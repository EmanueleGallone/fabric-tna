# Copyright 2013-2018 Barefoot Networks, Inc.
# SPDX-License-Identifier: Apache-2.0


#
# Antonin Bas (antonin@barefootnetworks.com)
#
#

import math
import os
import queue
import random
import socket
import struct
import sys
import threading
import time
from collections import Counter
from functools import partial, partialmethod, wraps
from io import StringIO
from unittest import SkipTest

import google.protobuf.text_format
import grpc
import ptf
import ptf.testutils as testutils
import scapy.packet
import scapy.utils
from google.rpc import code_pb2, status_pb2
from p4.config.v1 import p4info_pb2
from p4.v1 import p4runtime_pb2, p4runtime_pb2_grpc
from ptf import config
from ptf.base_tests import BaseTest
from ptf.dataplane import match_exp_pkt
from scapy.layers.l2 import Ether

# PTF-to-TestVector translation utils
# https://github.com/stratum/testvectors/tree/master/utils/python
from testvector import tvutils

RPC_TIMEOUT = 10  # used when sending Write/Read requests.

# Convert integer (with length) to binary byte string
def stringify(n, length):
    return n.to_bytes(length, byteorder="big")


def is_v1model():
    # using parameter 'pltfm' to get information if running for bmv2.
    _is_bmv2 = testutils.test_param_get("pltfm")
    return _is_bmv2 == "bmv2"


def is_tna():
    return not is_v1model()


def ipv4_to_binary(addr):
    return socket.inet_aton(addr)


def mac_to_binary(addr):
    return bytes.fromhex(addr.replace(":", ""))


def format_pkt_match(received_pkt, expected_pkt):
    # Taken from PTF dataplane class
    stdout_save = sys.stdout
    try:
        # The scapy packet dissection methods print directly to stdout,
        # so we have to redirect stdout to a string.
        sys.stdout = StringIO()

        print("========== EXPECTED ==========")
        if isinstance(expected_pkt, scapy.packet.Packet):
            scapy.packet.ls(expected_pkt)
            print("--")
        scapy.utils.hexdump(expected_pkt)
        print("========== RECEIVED ==========")
        if isinstance(received_pkt, scapy.packet.Packet):
            scapy.packet.ls(received_pkt)
            print("--")
        scapy.utils.hexdump(received_pkt)
        print("==============================")

        return sys.stdout.getvalue()
    finally:
        sys.stdout.close()
        sys.stdout = stdout_save  # Restore the original stdout.


def format_exp_rcv(expected, received):
    buf = ""
    buf += "========== EXPECTED ==========\n"
    buf += str(expected)
    buf += "========== RECEIVED ==========\n"
    buf += str(received)
    buf += "=============================="
    return buf


def get_controller_packet_metadata(p4info, meta_type, name):
    """
    This method retrieves the controller metadata from a p4info file.
    :param p4info: The p4info file
    :param meta_type: The type of metadata (e.g. packet_in)
    :param name: The name of the metadata to retrieve (e.g. bitwidth)
    :return: The controller metadata.
    """
    for t in p4info.controller_packet_metadata:
        pre = t.preamble
        if pre.name == meta_type:
            for m in t.metadata:
                if name is not None:
                    if m.name == name:
                        return m


def de_canonicalize_bytes(bitwidth: int, input: bytes):
    """
    This method adds a padding to the 'input' param.
    Needed for bmv2 since it uses Canonical Bytestrings: this representation
    trims the data to the lowest amount of bytes needed for that particular value
    (e.g. 0x0 for PacketIn.ingress_port will be interpreted by Stratum bmv2 using 1 byte, instead of 9 bits,
    as declared in header.p4)
    :param bitwidth: the desired size of input.
    :param input: the byte string to be padded.
    :return: padded input with bytes such that: len(bin(input)) >= bitwidth.
    """
    if bitwidth <= 0:
        raise ValueError("bitwidth must be a positive integer.")
    if input is None:
        raise ValueError("input cannot be of NoneType.")

    byte_width = (
        bitwidth + 7
    ) // 8  # use integer division to avoid floating point rounding errors.
    return input.rjust(byte_width, b"\0")  # right padding <-> BigEndian


# Workaround to choose byte size of port-related fields.
# TODO: Remove when canonical value is supported on both Stratum and ONOS.
PORT_SIZE_BYTES = 4 if is_tna() else 2
PORT_SIZE_BITS = 32 if is_tna() else 9

# Used to indicate that the gRPC error Status object returned by the server has
# an incorrect format.
class P4RuntimeErrorFormatException(Exception):
    def __init__(self, message):
        super(P4RuntimeErrorFormatException, self).__init__(message)


# Used to iterate over the p4.Error messages in a gRPC error Status object
class P4RuntimeErrorIterator:
    def __init__(self, grpc_error):
        assert grpc_error.code() == grpc.StatusCode.UNKNOWN
        self.grpc_error = grpc_error

        error = None
        # The gRPC Python package does not have a convenient way to access the
        # binary details for the error: they are treated as trailing metadata.
        for meta in self.grpc_error.trailing_metadata():
            if meta[0] == "grpc-status-details-bin":
                error = status_pb2.Status()
                error.ParseFromString(meta[1])
                break
        if error is None:
            raise P4RuntimeErrorFormatException("No binary details field")

        # if len(error.details) == 0:
        #     raise P4RuntimeErrorFormatException(
        #         "Binary details field has empty Any details repeated field")
        self.errors = error.details
        self.idx = 0

    def __iter__(self):
        return self

    def __next__(self):
        while self.idx < len(self.errors):
            p4_error = p4runtime_pb2.Error()
            one_error_any = self.errors[self.idx]
            if not one_error_any.Unpack(p4_error):
                raise P4RuntimeErrorFormatException(
                    "Cannot convert Any message to p4.Error"
                )
            if p4_error.canonical_code == code_pb2.OK:
                self.idx += 1
                continue
            v = self.idx, p4_error
            self.idx += 1
            return v
        raise StopIteration


# P4Runtime uses a 3-level message in case of an error during the processing of
# a write batch. This means that if we do not wrap the grpc.RpcError inside a
# custom exception, we can end-up with a non-helpful exception message in case
# of failure as only the first level will be printed. In this custom exception
# class, we extract the nested error message (one for each operation included
# in the batch) in order to print error code + user-facing message.
# See P4 Runtime documentation for more details on error-reporting.
class P4RuntimeException(Exception):
    def __init__(self, grpc_error):
        assert grpc_error.code() == grpc.StatusCode.UNKNOWN
        super(P4RuntimeException, self).__init__()
        self.grpc_error = grpc_error
        self.errors = []
        try:
            error_iterator = P4RuntimeErrorIterator(grpc_error)
            for error_tuple in error_iterator:
                self.errors.append(error_tuple)
        except P4RuntimeErrorFormatException:
            raise  # just propagate exception for now

    def __str__(self):
        message = "Error(s) during RPC: {} {}\n".format(
            self.grpc_error.code(), self.grpc_error.details()
        )
        for idx, p4_error in self.errors:
            code_name = code_pb2._CODE.values_by_number[p4_error.canonical_code].name
            message += "\t* At index {}: {}, '{}'\n".format(
                idx, code_name, p4_error.message
            )
        return message


# This code is common to all tests. setUp() is invoked at the beginning of the
# test and tearDown is called at the end, no matter whether the test passed /
# failed / errored.
# noinspection PyUnresolvedReferences
class P4RuntimeTest(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
        self._swports = []
        for device, port, ifname in config["interfaces"]:
            self._swports.append(port)

        grpc_addr = testutils.test_param_get("grpcaddr")
        if grpc_addr is None:
            grpc_addr = "localhost:50051"

        self.device_id = int(testutils.test_param_get("device_id"))
        if self.device_id is None:
            self.fail("Device ID is not set")

        self.cpu_port = int(testutils.test_param_get("cpu_port"))
        if self.cpu_port is None:
            self.fail("CPU port is not set")

        pltfm = testutils.test_param_get("pltfm")
        if pltfm is not None and pltfm == "hw" and getattr(self, "_skip_on_hw", False):
            raise SkipTest("Skipping test in HW")

        proto_txt_path = testutils.test_param_get("p4info")
        # print("Importing p4info proto from {}".format(proto_txt_path))
        self.p4info = p4info_pb2.P4Info()
        with open(proto_txt_path, "rb") as fin:
            google.protobuf.text_format.Merge(fin.read(), self.p4info)

        self.import_p4info_names()

        # used to store write requests sent to the P4Runtime server, useful for
        # autocleanup of tests (see definition of autocleanup decorator below)
        self.reqs = []

        self.election_id = 1
        if testutils.test_param_get("generate_tv") == "True":
            self.generate_tv = True
        else:
            self.generate_tv = False
        if testutils.test_param_get("loopback") == "True":
            self.loopback = True
        else:
            self.loopback = False
        if self.generate_tv:
            self.tv_list = []
            self.tv_name = self.__class__.__name__
        else:
            # Setting up PTF dataplane
            self.dataplane = ptf.dataplane_instance
            self.dataplane.flush()
            self.channel = grpc.insecure_channel(grpc_addr)
            self.stub = p4runtime_pb2_grpc.P4RuntimeStub(self.channel)
            self.set_up_stream()

    # In order to make writing tests easier, we accept any suffix that uniquely
    # identifies the object among p4info objects of the same type.
    def import_p4info_names(self):
        self.p4info_obj_map = {}
        self.p4info_id_to_name = {}
        suffix_count = Counter()
        for p4_obj_type in [
            "tables",
            "action_profiles",
            "actions",
            "counters",
            "meters",
            "direct_counters",
            "registers",
        ]:
            for obj in getattr(self.p4info, p4_obj_type):
                pre = obj.preamble
                suffix = None
                for s in reversed(pre.name.split(".")):
                    suffix = s if suffix is None else s + "." + suffix
                    key = (p4_obj_type, suffix)
                    self.p4info_obj_map[key] = obj
                    suffix_count[key] += 1
                self.p4info_id_to_name[pre.id] = pre.name
        for key, c in suffix_count.items():
            if c > 1:
                del self.p4info_obj_map[key]

    def set_up_stream(self):
        self.stream_out_q = queue.Queue()
        self.stream_in_q = queue.Queue()

        def stream_req_iterator():
            while True:
                p = self.stream_out_q.get()
                if p is None:
                    break
                yield p

        def stream_recv(stream):
            for p in stream:
                self.stream_in_q.put(p)

        self.stream = self.stub.StreamChannel(stream_req_iterator())
        self.stream_recv_thread = threading.Thread(
            target=stream_recv, args=(self.stream,)
        )
        self.stream_recv_thread.start()

        self.handshake()

    def handshake(self):
        req = p4runtime_pb2.StreamMessageRequest()
        arbitration = req.arbitration
        arbitration.device_id = self.device_id
        election_id = arbitration.election_id
        election_id.high = 0
        election_id.low = self.election_id
        self.stream_out_q.put(req)

        rep = self.get_stream_packet("arbitration", timeout=2)
        if rep is None:
            self.fail("Failed to establish handshake")

    def tearDown(self):
        if self.generate_tv:
            tvutils.write_tv_list_to_files(self.tv_list, os.getcwd(), self.tv_name)
        else:
            self.tear_down_stream()
        BaseTest.tearDown(self)

    def tear_down_stream(self):
        self.stream_out_q.put(None)
        self.stream_recv_thread.join()

    def get_packet_in(self, timeout=2):
        msg = self.get_stream_packet("packet", timeout)
        if msg is None:
            self.fail("Packet in not received")
        else:
            return msg.packet

    def verify_packet_in(self, exp_pkt, exp_in_port, timeout=2):
        if self.generate_tv:
            exp_pkt_in = p4runtime_pb2.PacketIn()
            exp_pkt_in.payload = bytes(exp_pkt)
            ingress_physical_port = exp_pkt_in.metadata.add()
            ingress_physical_port.metadata_id = 0
            ingress_physical_port.value = stringify(exp_in_port, PORT_SIZE_BYTES)
            tvutils.add_packet_in_expectation(self.tc, exp_pkt_in)
        else:
            pkt_in_msg = self.get_packet_in(timeout=timeout)
            rx_in_port_ = pkt_in_msg.metadata[0].value

            # Here we only compare the integer value of ingress port metadata instead
            # of the byte string.
            if is_tna():
                rx_inport = struct.unpack("!I", rx_in_port_)[0]
            else:
                pkt_in_metadata = get_controller_packet_metadata(
                    self.p4info, meta_type="packet_in", name="ingress_port"
                )
                pkt_in_ig_port_bitwidth = pkt_in_metadata.bitwidth
                rx_in_port_ = de_canonicalize_bytes(
                    pkt_in_ig_port_bitwidth, rx_in_port_
                )
                rx_inport = struct.unpack("!H", rx_in_port_)[0]

            if exp_in_port != rx_inport:
                self.fail(
                    "Wrong packet-in ingress port, "
                    + "expected {} but received was {}".format(exp_in_port, rx_inport)
                )
            rx_pkt = Ether(pkt_in_msg.payload)
            if not match_exp_pkt(exp_pkt, rx_pkt):
                self.fail(
                    "Received packet-in is not the expected one\n"
                    + format_pkt_match(rx_pkt, exp_pkt)
                )

    def verify_packet_out(self, pkt, out_port):
        self.send_packet_out(self.build_packet_out(pkt, out_port))
        self.verify_packet(pkt, out_port)

    def verify_p4runtime_entity(self, expected, received):
        if not self.generate_tv and expected != received:
            self.fail(
                "Received entity is not the expected one\n"
                + format_exp_rcv(expected, received)
            )

    def verify_no_other_packets(self):
        if not self.generate_tv:
            testutils.verify_no_other_packets(self)

    def get_stream_packet(self, type_, timeout=1):
        start = time.time()
        try:
            while True:
                remaining = timeout - (time.time() - start)
                if remaining < 0:
                    break
                msg = self.stream_in_q.get(timeout=remaining)
                if not msg.HasField(type_):
                    continue
                return msg
        except Exception:  # timeout expired
            pass
        return None

    def send_packet_out(self, packet):
        packet_out_req = p4runtime_pb2.StreamMessageRequest()
        packet_out_req.packet.CopyFrom(packet)
        if self.generate_tv:
            tvutils.add_packet_out_operation(self.tc, packet)
        else:
            self.stream_out_q.put(packet_out_req)

    def swports(self, idx):
        if idx >= len(self._swports):
            self.fail("Index {} is out-of-bound of port map".format(idx))
        return self._swports[idx]

    def get_obj(self, p4_obj_type, p4_name):
        key = (p4_obj_type, p4_name)
        obj = self.p4info_obj_map.get(key, None)
        if obj is None:
            raise Exception(
                "Unable to find {} '{}' in p4info".format(p4_obj_type, p4_name)
            )
        return obj

    def get_obj_id(self, p4_obj_type, p4_name):
        obj = self.get_obj(p4_obj_type, p4_name)
        return obj.preamble.id

    def get_obj_name_from_id(self, p4info_id):
        return self.p4info_id_to_name[p4info_id]

    def get_param_id(self, action_name, param_name):
        a = self.get_obj("actions", action_name)
        for p in a.params:
            if p.name == param_name:
                return p.id
        raise Exception(
            "Param '%s' not found in action '%s'" % (param_name, action_name)
        )

    def get_mf_id(self, table_name, mf_name):
        t = self.get_obj("tables", table_name)
        if t is None:
            return None
        for mf in t.match_fields:
            if mf.name == mf_name:
                return mf.id
        raise Exception(
            "Match field '%s' not found in table '%s'" % (mf_name, table_name)
        )

    def get_mf_bitwidth(self, table_name, mf_name):
        t = self.get_obj("tables", table_name)
        if t is None:
            return None
        for mf in t.match_fields:
            if mf.name == mf_name:
                return mf.bitwidth
        raise Exception(
            "Match field '%s' not found in table '%s'" % (mf_name, table_name)
        )

    def send_packet(self, port, pkt):
        if self.generate_tv:
            tvutils.add_traffic_stimulus(self.tc, port, pkt)
        else:
            testutils.send_packet(self, port, pkt)

    def verify_packet(self, exp_pkt, port):
        port_list = []
        port_list.append(port)
        if self.generate_tv:
            tvutils.add_traffic_expectation(self.tc, port_list, exp_pkt)
        else:
            testutils.verify_packet(self, exp_pkt, port)

    def verify_each_packet_on_each_port(self, packets, ports):
        if self.generate_tv:
            for i in range(len(packets)):
                port_list = []
                port_list.append(ports[i])
                tvutils.add_traffic_expectation(self.tc, port_list, packets[i])
        else:
            testutils.verify_each_packet_on_each_port(self, packets, ports)

    def verify_packets(self, pkt, ports):
        if self.generate_tv:
            for port in ports:
                port_list = []
                port_list.append(port)
                tvutils.add_traffic_expectation(self.tc, port_list, pkt)
        else:
            testutils.verify_packets(self, pkt, ports)

    def verify_any_packet_any_port(self, pkts, ports):
        if self.generate_tv:
            for pkt in pkts:
                tvutils.add_traffic_expectation(self.tc, ports, pkt)
            # workaround to return a port value
            return random.randint(0, 1)
        else:
            return testutils.verify_any_packet_any_port(self, pkts, ports)

    # These are attempts at convenience functions aimed at making writing
    # P4Runtime PTF tests easier.

    class MF(object):
        def __init__(self, mf_name):
            self.name = mf_name

        def check_value_size(self, value, bitwidth):
            v_int = int.from_bytes(value, "big")
            if v_int > ((1 << bitwidth) - 1):
                raise Exception(
                    f"Value {v_int} is too large for match field bitwidth {bitwidth}"
                )

    class Exact(MF):
        def __init__(self, mf_name, v):
            super(P4RuntimeTest.Exact, self).__init__(mf_name)
            self.v = v

        def add_to(self, mf_id, mk, bitwidth):
            self.check_value_size(self.v, bitwidth)
            mf = mk.add()
            mf.field_id = mf_id
            mf.exact.value = self.v

    class Lpm(MF):
        def __init__(self, mf_name, v, pLen):
            super(P4RuntimeTest.Lpm, self).__init__(mf_name)
            self.v = v
            self.pLen = pLen

        def add_to(self, mf_id, mk, bitwidth):
            # P4Runtime mandates that the match field should be omitted for
            # "don't care" LPM matches (i.e. when prefix length is zero)
            if self.pLen == 0:
                return
            self.check_value_size(self.v, bitwidth)
            if self.pLen > bitwidth:
                raise Exception(
                    f"Prefix length {self.pLen} too long for bitwidth {bitwidth}"
                )
            mf = mk.add()
            mf.field_id = mf_id
            mf.lpm.prefix_len = self.pLen
            mf.lpm.value = b""

            # P4Runtime now has strict rules regarding ternary matches: in the
            # case of LPM, trailing bits in the value (after prefix) must be set
            # to 0.
            first_byte_masked = self.pLen // 8
            for i in range(first_byte_masked):
                mf.lpm.value += stringify(self.v[i], 1)
            if first_byte_masked == len(self.v):
                return
            r = self.pLen % 8
            mf.lpm.value += stringify(self.v[first_byte_masked] & (0xFF << (8 - r)), 1)
            for i in range(first_byte_masked + 1, len(self.v)):
                mf.lpm.value += b"\x00"

    class Ternary(MF):
        def __init__(self, mf_name, v, mask):
            super(P4RuntimeTest.Ternary, self).__init__(mf_name)
            self.v = v
            self.mask = mask

        def add_to(self, mf_id, mk, bitwidth):
            # P4Runtime mandates that the match field should be omitted for
            # "don't care" ternary matches (i.e. when mask is zero)
            if all(c == 0 for c in self.mask):
                return
            self.check_value_size(self.v, bitwidth)
            mf = mk.add()
            mf.field_id = mf_id
            assert len(self.mask) == len(self.v)
            mf.ternary.mask = self.mask
            mf.ternary.value = b""
            # P4Runtime now has strict rules regarding ternary matches: in the
            # case of Ternary, "don't-care" bits in the value must be set to 0
            for i in range(len(self.mask)):
                mf.ternary.value += stringify(self.v[i] & self.mask[i], 1)

    class Range(MF):
        def __init__(self, mf_name, low, high):
            super(P4RuntimeTest.Range, self).__init__(mf_name)
            self.low = low
            self.high = high

        def add_to(self, mf_id, mk, bitwidth):
            # P4Runtime mandates that the match field should be omitted for
            # "don't care" range matches (i.e. when all possible values are
            # included in the range)
            self.check_value_size(self.low, bitwidth)
            self.check_value_size(self.high, bitwidth)
            low_is_zero = all(c == 0 for c in self.low)
            upper_bound = (1 << bitwidth) - 1
            high_is_max = self.high == upper_bound.to_bytes(
                math.ceil(bitwidth / 8), "big"
            )
            if low_is_zero and high_is_max:
                return
            mf = mk.add()
            mf.field_id = mf_id
            assert len(self.high) == len(self.low)
            mf.range.low = self.low
            mf.range.high = self.high

    # Sets the match key for a p4::TableEntry object. mk needs to be an
    # iterable object of MF instances
    def set_match_key(self, table_entry, t_name, mk):
        for mf in mk:
            mf_id = self.get_mf_id(t_name, mf.name)
            mf_bitwidth = self.get_mf_bitwidth(t_name, mf.name)
            mf.add_to(mf_id, table_entry.match, mf_bitwidth)

    def set_action(self, action, a_name, params):
        action.action_id = self.get_action_id(a_name)
        for p_name, v in params:
            param = action.params.add()
            param.param_id = self.get_param_id(a_name, p_name)
            param.value = v

    # Sets the action & action data for a p4::TableEntry object. params needs
    # to be an iterable object of 2-tuples (<param_name>, <value>).
    def set_action_entry(self, table_entry, a_name, params):
        self.set_action(table_entry.action.action, a_name, params)

    def _write(self, req):
        try:
            return self.stub.Write(req, timeout=RPC_TIMEOUT)
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.UNKNOWN:
                raise e
            raise P4RuntimeException(e)

    def read_request(self, req):
        entities = []
        if self.generate_tv:
            return entities
        else:
            try:
                for resp in self.stub.Read(req, timeout=RPC_TIMEOUT):
                    entities.extend(resp.entities)
            except grpc.RpcError as e:
                if e.code() != grpc.StatusCode.UNKNOWN:
                    raise e
                raise P4RuntimeException(e)
            return entities

    def write_request(self, req, store=True):
        if self.generate_tv:
            tvutils.add_write_operation(self.tc, req)
            if store:
                self.reqs.append(req)
            return None
        else:
            rep = self._write(req)
            if store:
                self.reqs.append(req)
            return rep

    def get_new_write_request(self):
        req = p4runtime_pb2.WriteRequest()
        req.device_id = self.device_id
        election_id = req.election_id
        election_id.high = 0
        election_id.low = self.election_id
        return req

    def get_new_read_request(self):
        req = p4runtime_pb2.ReadRequest()
        req.device_id = self.device_id
        return req

    def get_new_read_response(self):
        resp = p4runtime_pb2.ReadResponse()
        return resp

    #
    # Convenience functions to build and send P4Runtime write requests
    #

    def _push_update_member(self, req, ap_name, mbr_id, a_name, params, update_type):
        update = req.updates.add()
        update.type = update_type
        ap_member = update.entity.action_profile_member
        ap_member.action_profile_id = self.get_ap_id(ap_name)
        ap_member.member_id = mbr_id
        self.set_action(ap_member.action, a_name, params)

    def push_update_add_member(self, req, ap_name, mbr_id, a_name, params):
        self._push_update_member(
            req, ap_name, mbr_id, a_name, params, p4runtime_pb2.Update.INSERT
        )

    def send_request_add_member(self, ap_name, mbr_id, a_name, params):
        req = self.get_new_write_request()
        self.push_update_add_member(req, ap_name, mbr_id, a_name, params)
        return req, self.write_request(req)

    def push_update_modify_member(self, req, ap_name, mbr_id, a_name, params):
        self._push_update_member(
            req, ap_name, mbr_id, a_name, params, p4runtime_pb2.Update.MODIFY
        )

    def send_request_modify_member(self, ap_name, mbr_id, a_name, params):
        req = self.get_new_write_request()
        self.push_update_modify_member(req, ap_name, mbr_id, a_name, params)
        return req, self.write_request(req, store=False)

    def push_update_modify_group(self, req, ap_name, grp_id, grp_size, mbr_ids):
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.MODIFY
        ap_group = update.entity.action_profile_group
        ap_group.action_profile_id = self.get_ap_id(ap_name)
        ap_group.group_id = grp_id
        for mbr_id in mbr_ids:
            member = ap_group.members.add()
            member.member_id = mbr_id
            member.weight = 1
        ap_group.max_size = grp_size

    def send_request_modify_group(self, ap_name, grp_id, grp_size=32, mbr_ids=()):
        req = self.get_new_write_request()
        self.push_update_modify_group(req, ap_name, grp_id, grp_size, mbr_ids)
        return req, self.write_request(req, store=False)

    def push_update_add_group(self, req, ap_name, grp_id, grp_size=32, mbr_ids=()):
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.INSERT
        ap_group = update.entity.action_profile_group
        ap_group.action_profile_id = self.get_ap_id(ap_name)
        ap_group.group_id = grp_id
        ap_group.max_size = grp_size
        for mbr_id in mbr_ids:
            member = ap_group.members.add()
            member.member_id = mbr_id
            member.weight = 1

    def send_request_add_group(self, ap_name, grp_id, grp_size=32, mbr_ids=()):
        req = self.get_new_write_request()
        self.push_update_add_group(req, ap_name, grp_id, grp_size, mbr_ids)
        return req, self.write_request(req)

    def push_update_set_group_membership(self, req, ap_name, grp_id, mbr_ids=()):
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.MODIFY
        ap_group = update.entity.action_profile_group
        ap_group.action_profile_id = self.get_ap_id(ap_name)
        ap_group.group_id = grp_id
        for mbr_id in mbr_ids:
            member = ap_group.members.add()
            member.member_id = mbr_id

    def send_request_set_group_membership(self, ap_name, grp_id, mbr_ids=()):
        req = self.get_new_write_request()
        self.push_update_set_group_membership(req, ap_name, grp_id, mbr_ids)
        return req, self.write_request(req, store=False)

    def push_update_add_entry_to_action(
        self, req, t_name, mk, a_name, params, priority=0
    ):
        update = req.updates.add()
        table_entry = update.entity.table_entry
        table_entry.table_id = self.get_table_id(t_name)
        table_entry.priority = priority
        if mk is None or len(mk) == 0:
            table_entry.is_default_action = True
            update.type = p4runtime_pb2.Update.MODIFY
        else:
            update.type = p4runtime_pb2.Update.INSERT
            self.set_match_key(table_entry, t_name, mk)
        self.set_action_entry(table_entry, a_name, params)

    def send_request_add_entry_to_action(self, t_name, mk, a_name, params, priority=0):
        req = self.get_new_write_request()
        self.push_update_add_entry_to_action(req, t_name, mk, a_name, params, priority)
        return req, self.write_request(req)

    def push_update_add_entry_to_member(self, req, t_name, mk, mbr_id):
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.INSERT
        table_entry = update.entity.table_entry
        table_entry.table_id = self.get_table_id(t_name)
        self.set_match_key(table_entry, t_name, mk)
        table_entry.action.action_profile_member_id = mbr_id

    def send_request_add_entry_to_member(self, t_name, mk, mbr_id):
        req = self.get_new_write_request()
        self.push_update_add_entry_to_member(req, t_name, mk, mbr_id)
        return req, self.write_request(req)

    def push_update_add_entry_to_group(self, req, t_name, mk, grp_id):
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.INSERT
        table_entry = update.entity.table_entry
        table_entry.table_id = self.get_table_id(t_name)
        self.set_match_key(table_entry, t_name, mk)
        table_entry.action.action_profile_group_id = grp_id

    def send_request_add_entry_to_group(self, t_name, mk, grp_id):
        req = self.get_new_write_request()
        self.push_update_add_entry_to_group(req, t_name, mk, grp_id)
        return req, self.write_request(req)

    def read_direct_counter(self, table_entry):
        req = self.get_new_read_request()
        entity = req.entities.add()
        direct_counter_entry = entity.direct_counter_entry
        direct_counter_entry.table_entry.CopyFrom(table_entry)

        for entity in self.read_request(req):
            if entity.HasField("direct_counter_entry"):
                return entity.direct_counter_entry
        return None

    def write_direct_counter(self, table_entry, byte_count, packet_count):
        req = self.get_new_write_request()
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.MODIFY
        direct_counter_entry = update.entity.direct_counter_entry
        direct_counter_entry.table_entry.CopyFrom(table_entry)
        direct_counter_entry.data.byte_count = byte_count
        direct_counter_entry.data.packet_count = packet_count
        return req, self.write_request(req, store=False)

    def read_indirect_counter(self, c_name, c_index, typ):
        # Check counter type with P4Info
        counter = self.get_counter(c_name)
        counter_type_unit = p4info_pb2.CounterSpec.Unit.items()[counter.spec.unit][0]
        if counter_type_unit != "BOTH" and counter_type_unit != typ:
            raise Exception(
                "Counter "
                + c_name
                + " is of type "
                + counter_type_unit
                + ", but requested: "
                + typ
            )
        req = self.get_new_read_request()
        entity = req.entities.add()
        counter_entry = entity.counter_entry
        c_id = self.get_counter_id(c_name)
        counter_entry.counter_id = c_id
        index = counter_entry.index
        index.index = c_index

        for entity in self.read_request(req):
            if entity.HasField("counter_entry"):
                return entity.counter_entry
        return None

    def write_indirect_counter(
        self, c_name, c_index, byte_count=None, packet_count=None
    ):
        # Get counter type with P4Info
        counter = self.get_counter(c_name)
        counter_type_unit = p4info_pb2.CounterSpec.Unit.items()[counter.spec.unit][0]

        req = self.get_new_write_request()
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.MODIFY
        counter_entry = update.entity.counter_entry

        c_id = self.get_counter_id(c_name)
        counter_entry.counter_id = c_id
        index = counter_entry.index
        index.index = c_index

        counter_data = counter_entry.data

        if counter_type_unit == "BOTH" or counter_type_unit == "BYTES":
            if byte_count is None:
                raise Exception(
                    "Counter "
                    + c_name
                    + " is of type "
                    + counter_type_unit
                    + ", byte_count cannot be None"
                )
            counter_data.byte_count = byte_count
        if counter_type_unit == "BOTH" or counter_type_unit == "PACKETS":
            if packet_count is None:
                raise Exception(
                    "Counter "
                    + c_name
                    + " is of type "
                    + counter_type_unit
                    + ", packet_count cannot be None"
                )
            counter_data.packet_count = packet_count
        return req, self.write_request(req, store=False)

    def write_indirect_meter(self, m_name, m_index, cir, cburst, pir, pburst):
        req = self.get_new_write_request()
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.MODIFY
        meter_entry = update.entity.meter_entry

        m_id = self.get_meter_id(m_name)
        meter_entry.meter_id = m_id
        index = meter_entry.index
        index.index = m_index

        config = meter_entry.config
        config.cir = cir
        config.cburst = cburst
        config.pir = pir
        config.pburst = pburst

        return req, self.write_request(req)

    def read_table_entry(self, t_name, mk, priority=0):
        req = self.get_new_read_request()
        entity = req.entities.add()
        table_entry = entity.table_entry
        table_entry.table_id = self.get_table_id(t_name)
        table_entry.priority = priority
        if mk is None or len(mk) == 0:
            table_entry.is_default_action = True
        else:
            self.set_match_key(table_entry, t_name, mk)

        for entity in self.read_request(req):
            if entity.HasField("table_entry"):
                return entity.table_entry
        return None

    def read_action_profile_member(self, ap_name, mbr_id):
        req = self.get_new_read_request()
        entity = req.entities.add()
        action_profile_member = entity.action_profile_member
        action_profile_member.action_profile_id = self.get_ap_id(ap_name)
        action_profile_member.member_id = mbr_id

        for entity in self.read_request(req):
            if entity.HasField("action_profile_member"):
                return entity.action_profile_member
        return None

    def read_action_profile_group(self, ap_name, grp_id):
        req = self.get_new_read_request()
        entity = req.entities.add()
        action_profile_member = entity.action_profile_group
        action_profile_member.action_profile_id = self.get_ap_id(ap_name)
        action_profile_member.group_id = grp_id

        for entity in self.read_request(req):
            if entity.HasField("action_profile_group"):
                return entity.action_profile_group
        return None

    def write_register(self, register_name, index, data):
        req = self.get_new_write_request()
        update = req.updates.add()
        update.type = p4runtime_pb2.Update.MODIFY
        register = update.entity.register_entry
        register.register_id = self.get_register_id(register_name)
        register.index.index = index
        register.data.bitstring = data
        return req, self.write_request(req)

    # Reads the register value with a given register name and an index.
    # Note that due to the limitation of P4Runtime protocol, we can only read
    # the register value from the first pipeline(pipe 0).
    def read_register(self, register_name, index):
        req = self.get_new_read_request()
        entity = req.entities.add()
        register = entity.register_entry
        register.register_id = self.get_register_id(register_name)
        register.index.index = index

        for entity in self.read_request(req):
            if entity.HasField("register_entry"):
                return entity.register_entry
        return None

    def verify_action_profile_group(
        self, ap_name, grp_id, expected_action_profile_group
    ):
        req = self.get_new_read_request()
        entity = req.entities.add()
        action_profile_member = entity.action_profile_group
        action_profile_member.action_profile_id = self.get_ap_id(ap_name)
        action_profile_member.group_id = grp_id

        if self.generate_tv:
            exp_resp = self.get_new_read_response()
            entity = exp_resp.entities.add()
            entity.action_profile_group.CopyFrom(expected_action_profile_group)
            # add to list
            exp_resps = []
            exp_resps.append(exp_resp)
            tvutils.add_read_expectation(self.tc, req, exp_resps)
            return None
        for entity in self.read_request(req):
            if entity.HasField("action_profile_group"):
                self.verify_p4runtime_entity(
                    entity.action_profile_group, expected_action_profile_group
                )
        return None

    def verify_multicast_group(self, group_id, expected_multicast_group):
        req = self.get_new_read_request()
        entity = req.entities.add()
        multicast_group = entity.packet_replication_engine_entry.multicast_group_entry
        multicast_group.multicast_group_id = group_id

        if self.generate_tv:
            exp_resp = self.get_new_read_response()
            entity = exp_resp.entities.add()
            entity.packet_replication_engine_entry.multicast_group_entry.CopyFrom(
                expected_multicast_group
            )
            # add to list
            exp_resps = []
            exp_resps.append(exp_resp)
            tvutils.add_read_expectation(self.tc, req, exp_resps)
            return None
        for entity in self.read_request(req):
            if entity.HasField("packet_replication_engine_entry"):
                pre_entry = entity.packet_replication_engine_entry
                if pre_entry.HasField("multicast_group_entry"):
                    self.verify_p4runtime_entity(
                        pre_entry.multicast_group_entry, expected_multicast_group,
                    )

    def verify_direct_counter(
        self, table_entry, expected_byte_count, expected_packet_count
    ):
        req = self.get_new_read_request()
        entity = req.entities.add()
        direct_counter_entry = entity.direct_counter_entry
        direct_counter_entry.table_entry.CopyFrom(table_entry)

        if self.generate_tv:
            exp_resp = self.get_new_read_response()
            entity = exp_resp.entities.add()
            entity.direct_counter_entry.table_entry.CopyFrom(table_entry)
            entity.direct_counter_entry.data.byte_count = expected_byte_count
            entity.direct_counter_entry.data.packet_count = expected_packet_count
            # add to list
            exp_resps = []
            exp_resps.append(exp_resp)
            tvutils.add_read_expectation(self.tc, req, exp_resps)
            return None

        for entity in self.read_request(req):
            if entity.HasField("direct_counter_entry"):
                direct_counter = entity.direct_counter_entry
                if (
                    direct_counter.data.byte_count != expected_byte_count
                    or direct_counter.data.packet_count != expected_packet_count
                ):
                    self.fail("Incorrect direct counter value:\n" + str(direct_counter))
        return None

    def verify_indirect_counter(
        self, c_name, c_index, typ, expected_byte_count=0, expected_packet_count=0,
    ):
        # Check counter type with P4Info
        counter = self.get_counter(c_name)
        counter_type_unit = p4info_pb2.CounterSpec.Unit.items()[counter.spec.unit][0]
        if counter_type_unit != "BOTH" and counter_type_unit != typ:
            raise Exception(
                "Counter "
                + c_name
                + " is of type "
                + counter_type_unit
                + ", but requested: "
                + typ
            )
        req = self.get_new_read_request()
        entity = req.entities.add()
        counter_entry = entity.counter_entry
        c_id = self.get_counter_id(c_name)
        counter_entry.counter_id = c_id
        index = counter_entry.index
        index.index = c_index

        if self.generate_tv:
            exp_resp = self.get_new_read_response()
            entity = exp_resp.entities.add()
            entity.counter_entry.CopyFrom(counter_entry)
            entity.counter_entry.data.byte_count = expected_byte_count
            entity.counter_entry.data.packet_count = expected_packet_count
            # add to list
            exp_resps = []
            exp_resps.append(exp_resp)
            tvutils.add_read_expectation(self.tc, req, exp_resps)
            return None

        for entity in self.read_request(req):
            if entity.HasField("counter_entry"):
                counter_entry = entity.counter_entry
                if (
                    counter_entry.data.byte_count != expected_byte_count
                    or counter_entry.data.packet_count != expected_packet_count
                ):
                    self.fail(
                        "%s value at index %d is not same as expected.\
                        \nActual packet count: %d, Expected packet count: %d\
                        \nActual byte count: %d, Expected byte count: %d\n"
                        % (
                            c_name,
                            c_index,
                            counter_entry.data.packet_count,
                            expected_packet_count,
                            counter_entry.data.byte_count,
                            expected_byte_count,
                        )
                    )
        return None

    def verify_register(
        self, register_name, register_index, expected_value,
    ):
        req = self.get_new_read_request()
        entity = req.entities.add()
        register_entry = entity.register_entry
        register_entry.register_id = self.get_register_id(register_name)
        register_entry.index.index = register_index

        if self.generate_tv:
            exp_resp = self.get_new_read_response()
            entity = exp_resp.entities.add()
            entity.register_entry.CopyFrom(register_entry)
            entity.register_entry.data.bitstring = expected_value

            # add to list
            exp_resps = []
            exp_resps.append(exp_resp)
            tvutils.add_read_expectation(self.tc, req, exp_resps)
            return None

        for entity in self.read_request(req):
            if entity.HasField("register_entry"):
                actual = int.from_bytes(entity.register_entry.data.bitstring, "big")
                expected = int.from_bytes(expected_value, "big")
                self.failIf(
                    expected != actual,
                    f"Expected register value: {expected}, actual: {actual}",
                )

        return None

    def is_default_action_update(self, update):
        return (
            update.type == p4runtime_pb2.Update.MODIFY
            and update.entity.WhichOneof("entity") == "table_entry"
            and update.entity.table_entry.is_default_action
        )

    def is_meter_update(self, update):
        return (
            update.type == p4runtime_pb2.Update.MODIFY
            and update.entity.WhichOneof("entity") == "meter_entry"
        )

    # iterates over all requests in reverse order; if they are INSERT updates,
    # replay them as DELETE updates; this is a convenient way to clean-up a lot
    # of switch state
    def undo_write_requests(self, reqs, create_new_tv=True):
        updates = []
        for req in reversed(reqs):
            for update in reversed(req.updates):
                if (
                    update.type == p4runtime_pb2.Update.INSERT
                    or self.is_default_action_update(update)
                    or self.is_meter_update(update)
                ):
                    updates.append(update)
        new_req = self.get_new_write_request()
        for update in updates:
            if self.is_default_action_update(update):
                # Reset table default entry to original one
                update.entity.table_entry.ClearField("action")
            elif self.is_meter_update(update):
                # Reset meter entry to the default one (all packets GREEN)
                update.entity.meter_entry.ClearField("config")
            else:
                update.type = p4runtime_pb2.Update.DELETE
            new_req.updates.add().CopyFrom(update)
        if self.generate_tv:
            if len(reqs) != 0:
                if create_new_tv:
                    self.tc = tvutils.get_new_testcase(self.tv)
                    self.tc.test_case_id = "Undo Write Requests"
                tvutils.add_write_operation(self.tc, new_req)
        else:
            self._write(new_req)


# Add p4info object and object id "getters" for each object type; these are
# just wrappers around P4RuntimeTest.get_obj and P4RuntimeTest.get_obj_id.
# For example: get_table(x) and get_table_id(x) respectively call
# get_obj("tables", x) and get_obj_id("tables", x)
for obj_type, nickname in [
    ("tables", "table"),
    ("action_profiles", "ap"),
    ("actions", "action"),
    ("counters", "counter"),
    ("meters", "meter"),
    ("direct_counters", "direct_counter"),
    ("registers", "register"),
]:
    name = "_".join(["get", nickname])
    setattr(P4RuntimeTest, name, partialmethod(P4RuntimeTest.get_obj, obj_type))
    name = "_".join(["get", nickname, "id"])
    setattr(P4RuntimeTest, name, partialmethod(P4RuntimeTest.get_obj_id, obj_type))


# this decorator can be used on the runTest method of P4Runtime PTF tests
# when it is used, the undo_write_requests will be called at the end of the
# test (irrespective of whether the test was a failure, a success, or an
# exception was raised). When this is used, all write requests must be
# performed through one of the send_request_* convenience functions, or by
# calling write_request; do not use stub.Write directly!
# most of the time, it is a great idea to use this decorator, as it makes the
# tests less verbose. In some circumstances, it is difficult to use it, in
# particular when the test itself issues DELETE request to remove some
# objects. In this case you will want to do the cleanup yourself (in the
# tearDown function for example); you can still use undo_write_request which
# should make things easier.
# because the PTF test writer needs to choose whether or not to use
# autocleanup, it seems more appropriate to define a decorator for this rather
# than do it unconditionally in the P4RuntimeTest tearDown method.
def autocleanup(f):
    @wraps(f)
    def handle(*args, **kwargs):
        test = args[0]
        assert isinstance(test, P4RuntimeTest)
        try:
            return f(*args, **kwargs)
        finally:
            test.undo_write_requests(test.reqs)
            test.reqs = []

    return handle


# this decorator should be used on the runTest method of P4Runtime PTF tests
# on using this decorator, new testvector instance is initiated before running
# runTest method and finally generated testvector is appended to list which
# will be written to files in the P4RuntimeTest tearDown method.
def tvsetup(f):
    @wraps(f)
    def handle(*args, **kwargs):
        test = args[0]
        assert isinstance(test, P4RuntimeTest)
        try:
            if test.generate_tv:
                if "tc_name" in kwargs:
                    test.tv = tvutils.get_new_testvector()
                    test.tc = tvutils.get_new_testcase(test.tv, kwargs["tc_name"])
                else:
                    test.tv = tvutils.get_new_testvector()
                    test.tc = tvutils.get_new_testcase(test.tv, test.tv_name)
            return f(*args, **kwargs)
        finally:
            if test.generate_tv:
                test.tv_list.append(test.tv)

    return handle


# This decorator should be used on the runTest method of P4Runtime PTF tests.
# On using this decorator TestVector generation is skipped for the test.
# This doesn't change the current behavior for executing ptf tests.
def tvskip(f):
    @wraps(f)
    def handle(*args, **kwargs):
        test = args[0]
        assert isinstance(test, P4RuntimeTest)
        if testutils.test_param_get("generate_tv") == "True":
            raise SkipTest("TestVector generation for " + str(test))
        return f(*args, **kwargs)

    return handle


# This decorator should be used for creating standalone TestVectors.
# On using this decorator TestVectors are generated for the P4RT operations in
# the calling method.
# This doesn't change the current behavior for executing ptf tests.
def tvcreate(name):
    def wrapper(f):
        @wraps(f)
        def handle(*args, **kwargs):
            test = args[0]
            assert isinstance(test, P4RuntimeTest)
            try:
                if test.generate_tv:
                    # If name contains "/", last string is considered as
                    # tv_name and prefix is considered as sub directory to be
                    # created under testvectors/<ptf_test_class_name>
                    # e.g. If name argument is "setup/setup_switch_info" for
                    # FabricIPv4UnicastTest, the testvector is saved as
                    # testvectors/FabricIPv4UnicastTest/setup/setup_switch_info.pb.txt
                    names = name.rsplit("/", 1)
                    if len(names) > 1:
                        sub_dir = names[0]
                        tv_name = names[1]
                    else:
                        sub_dir = ""
                        tv_name = names[0]
                    test.tv = tvutils.get_new_testvector()
                    test.tc = tvutils.get_new_testcase(test.tv, tv_name)
                return f(*args, **kwargs)
            finally:
                if test.generate_tv:
                    tv_folder = os.path.join(
                        os.getcwd(), "testvectors", test.__class__.__name__, sub_dir,
                    )
                    tvutils.write_to_file(
                        test.tv, tv_folder, tv_name, create_tv_sub_dir=False
                    )

        return handle

    return wrapper


def skip_on_hw(cls):
    cls._skip_on_hw = True
    return cls
