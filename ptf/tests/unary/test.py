# Copyright 2013-2018 Barefoot Networks, Inc.
# Copyright 2018-present Open Networking Foundation
# SPDX-License-Identifier: Apache-2.0


import difflib
import time
from unittest import skip, skipIf

from base_test import PORT_SIZE_BYTES, autocleanup, is_v1model, tvsetup
from fabric_test import *  # noqa
from p4.config.v1 import p4info_pb2
from ptf.testutils import group
from scapy.contrib.gtp import GTP_U_Header
from scapy.layers.inet import IP
from scapy.layers.ppp import PPPoED


class FabricBridgingTest(BridgingTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, tagged1, tagged2, pkt, tc_name):
        self.runBridgingTest(tagged1, tagged2, pkt)

    def runTest(self):
        print("")
        for vlan_conf, tagged in vlan_confs.items():
            for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                pktlen = 120
                tc_name = pkt_type + "_VLAN_" + vlan_conf + "_" + str(pktlen)
                print("Testing {} packet with VLAN {}..".format(pkt_type, vlan_conf))
                pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
                    pktlen=pktlen
                )
                self.doRunTest(tagged[0], tagged[1], pkt, tc_name=tc_name)


class FabricBridgingPriorityTest(BridgingPriorityTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        self.runBridgingPriorityTest()


class FabricDoubleTaggedBridgingTest(DoubleTaggedBridgingTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, tc_name):
        self.runDoubleTaggedBridgingTest(pkt)

    def runTest(self):
        print("")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
            pktlen = 120
            tc_name = pkt_type + "_DOUBLE_TAGGED" + "_" + str(pktlen)
            print("Testing double tagged {} packet ..".format(pkt_type))
            pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(pktlen=pktlen)
            self.doRunTest(pkt, tc_name=tc_name)


@skip("XConnect Currently Unsupported")
@group("xconnect")
class FabricDoubleVlanXConnectTest(DoubleVlanXConnectTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, tc_name):
        self.runXConnectTest(pkt)

    def runTest(self):
        print("")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
            pktlen = 120
            tc_name = pkt_type + "_" + str(pktlen)
            print("Testing {} packet...".format(pkt_type))
            pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(pktlen=pktlen)
            self.doRunTest(pkt, tc_name=tc_name)


@group("multicast")
class FabricArpBroadcastUntaggedTest(ArpBroadcastTest):
    @tvsetup
    @autocleanup
    def runTest(self):

        self.runArpBroadcastTest(
            tagged_ports=[], untagged_ports=[self.port1, self.port2, self.port3],
        )


@group("multicast")
class FabricArpBroadcastTaggedTest(ArpBroadcastTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        self.runArpBroadcastTest(
            tagged_ports=[self.port1, self.port2, self.port3], untagged_ports=[],
        )


@group("multicast")
class FabricArpBroadcastMixedTest(ArpBroadcastTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        self.runArpBroadcastTest(
            tagged_ports=[self.port2, self.port3], untagged_ports=[self.port1]
        )


@group("multicast")
class FabricIPv4MulticastTest(IPv4MulticastTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, in_vlan, out_vlan):
        pkt = testutils.simple_udp_packet(
            eth_dst="01:00:5e:00:00:01", ip_dst="224.0.0.1"
        )
        in_port = self.port1
        out_ports = [self.port2, self.port3]
        self.runIPv4MulticastTest(pkt, in_port, out_ports, in_vlan, out_vlan)

    def runTest(self):
        self.doRunTest(None, None)
        self.doRunTest(None, 10)
        self.doRunTest(10, None)
        self.doRunTest(10, 10)
        self.doRunTest(10, 11)


class FabricIPv4UnicastTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, mac_dest, prefix_len, tagged1, tagged2, tc_name):
        self.runIPv4UnicastTest(
            pkt, mac_dest, prefix_len=prefix_len, tagged1=tagged1, tagged2=tagged2,
        )

    def runTest(self):
        self.runTestInternal(
            HOST2_IPV4, [PREFIX_DEFAULT_ROUTE, PREFIX_SUBNET, PREFIX_HOST]
        )

    def runTestInternal(self, ip_dst, prefix_list):
        print("")
        for vlan_conf, tagged in vlan_confs.items():
            for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                for prefix_len in prefix_list:
                    for pkt_len in [MIN_PKT_LEN, 1500]:
                        tc_name = (
                            pkt_type
                            + "_VLAN_"
                            + vlan_conf
                            + "_"
                            + ip_dst
                            + "/"
                            + str(prefix_len)
                            + "_"
                            + str(pkt_len)
                        )
                        print(
                            "Testing {} packet with VLAN {}, IP dest {}/{}, size {}...".format(
                                pkt_type, vlan_conf, ip_dst, prefix_len, pkt_len
                            )
                        )
                        pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                            eth_src=HOST1_MAC,
                            eth_dst=SWITCH_MAC,
                            ip_src=HOST1_IPV4,
                            ip_dst=ip_dst,
                            pktlen=pkt_len,
                        )
                        self.doRunTest(
                            pkt,
                            HOST2_MAC,
                            prefix_len,
                            tagged[0],
                            tagged[1],
                            tc_name=tc_name,
                        )


class FabricIPv4UnicastFromPacketOutTest(IPv4UnicastTest):
    """Packet-outs should be routed like regular packets when setting
    packet_out_header_t.do_forwarding=1
    """

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, mac_dest, tagged2, tc_name):
        self.runIPv4UnicastTest(
            pkt, mac_dest, tagged1=False, tagged2=tagged2, from_packet_out=True
        )

    def runTest(self):
        print("")
        # Cpu port is always considered untagged.
        for tagged2 in [False, True]:
            for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                tc_name = pkt_type + "_VLAN_" + str(tagged2)
                print("Testing {} packet, out-tagged={}...".format(pkt_type, tagged2))
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    eth_src=ZERO_MAC,
                    eth_dst=ZERO_MAC,
                    ip_src=HOST1_IPV4,
                    ip_dst=HOST2_IPV4,
                    pktlen=MIN_PKT_LEN,
                )
                self.doRunTest(
                    pkt=pkt, mac_dest=HOST2_MAC, tagged2=tagged2, tc_name=tc_name,
                )


class FabricIPv4UnicastDropTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, ig_port, eg_port, ipv4_dst, ipv4_len, pkt):
        self.setup_port(ig_port, 1, PORT_TYPE_EDGE)
        self.setup_port(eg_port, 1, PORT_TYPE_EDGE)
        self.set_forwarding_type(ig_port, SWITCH_MAC)
        self.add_forwarding_routing_v4_drop(
            ipv4_dstAddr=ipv4_dst, ipv4_pLen=ipv4_len,
        )
        self.send_packet(ig_port, pkt)
        self.verify_no_other_packets()

    def runTest(self):
        pkt = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        self.doRunTest(self.port1, self.port2, HOST2_IPV4, 32, pkt)


class FabricIPv4DropWithACLOverrideRoutingTest(IPv4UnicastTest):
    # ACL should override the actions made by previous table
    # pkts should be routed correctly
    @tvsetup
    @autocleanup
    def doRunTest(self, ig_port, eg_port, ipv4_dst, ipv4_len, pkt, exp_pkt):
        self.setup_port(ig_port, 1, PORT_TYPE_EDGE)
        self.setup_port(eg_port, 1, PORT_TYPE_EDGE)
        self.set_forwarding_type(ig_port, SWITCH_MAC)
        self.add_next_routing(400, eg_port, SWITCH_MAC, HOST2_MAC)
        self.add_forwarding_acl_next(
            next_id=400, ig_port_type=PORT_TYPE_EDGE, ipv4_dst=ipv4_dst
        )
        self.add_forwarding_routing_v4_drop(
            ipv4_dstAddr=ipv4_dst, ipv4_pLen=ipv4_len,
        )
        self.send_packet(ig_port, pkt)
        self.verify_packet(exp_pkt, eg_port)
        self.verify_no_other_packets()

    def runTest(self):
        pkt = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        exp_pkt = self.build_exp_ipv4_unicast_packet(pkt, HOST2_MAC)
        self.doRunTest(self.port1, self.port2, HOST2_IPV4, 32, pkt, exp_pkt)


class FabricIPv4DropWithACLOverrideOutputTest(IPv4UnicastTest):
    # ACL should override the actions made by previous table
    # pkts should be output correctly
    @tvsetup
    @autocleanup
    def doRunTest(self, ig_port, eg_port, ipv4_dst, ipv4_len, pkt, exp_pkt):
        self.setup_port(ig_port, 1, PORT_TYPE_EDGE)
        self.setup_port(eg_port, 1, PORT_TYPE_EDGE)
        self.set_forwarding_type(ig_port, SWITCH_MAC)
        self.add_forwarding_acl_set_output_port(eg_port, ipv4_dst=ipv4_dst)
        self.add_forwarding_routing_v4_drop(
            ipv4_dstAddr=ipv4_dst, ipv4_pLen=ipv4_len,
        )
        self.send_packet(ig_port, pkt)
        self.verify_packet(exp_pkt, eg_port)
        self.verify_no_other_packets()

    def runTest(self):
        pkt = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        # Although we are testing set output port (bridging)
        # the forwarding type is "Routing v4" because we need the v4 routing table
        exp_pkt = self.build_exp_ipv4_unicast_packet(pkt, SWITCH_MAC, HOST1_MAC)
        self.doRunTest(self.port1, self.port2, HOST2_IPV4, 32, pkt, exp_pkt)


class FabricIPv4UnicastDefaultRouteTest(FabricIPv4UnicastTest):
    def runTest(self):
        self.runTestInternal(DEFAULT_ROUTE_IPV4, [PREFIX_DEFAULT_ROUTE])


class FabricIPv4UnicastGroupTest(FabricTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(HOST2_IPV4, 24, 300)
        grp_id = 66
        mbrs = [
            (self.port2, SWITCH_MAC, HOST2_MAC),
            (self.port3, SWITCH_MAC, HOST3_MAC),
        ]
        self.add_next_routing_group(300, grp_id, mbrs)
        self.set_egress_vlan(self.port2, vlan_id, False)
        self.set_egress_vlan(self.port3, vlan_id, False)

        pkt_from1 = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        exp_pkt_to2 = testutils.simple_tcp_packet(
            eth_src=SWITCH_MAC,
            eth_dst=HOST2_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
        )
        exp_pkt_to3 = testutils.simple_tcp_packet(
            eth_src=SWITCH_MAC,
            eth_dst=HOST3_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
        )

        self.send_packet(self.port1, pkt_from1)
        self.verify_any_packet_any_port(
            [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
        )


class FabricIPv4UnicastGroupTestAllPortTcpSport(FabricTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        # In this test we check that packets are forwarded to all ports when we
        # change one of the 5-tuple header values. In this case tcp-source-port
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(HOST2_IPV4, 24, 300)
        grp_id = 66
        mbrs = [
            (self.port2, SWITCH_MAC, HOST2_MAC),
            (self.port3, SWITCH_MAC, HOST3_MAC),
        ]
        self.add_next_routing_group(300, grp_id, mbrs)
        self.set_egress_vlan(self.port2, vlan_id, False)
        self.set_egress_vlan(self.port3, vlan_id, False)
        # tcpsport_toport list is used to learn the tcp_source_port that
        # causes the packet to be forwarded for each port
        tcpsport_toport = [None, None]
        for i in range(50):
            test_tcp_sport = 1230 + i
            pkt_from1 = testutils.simple_tcp_packet(
                eth_src=HOST1_MAC,
                eth_dst=SWITCH_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=HOST2_IPV4,
                ip_ttl=64,
                tcp_sport=test_tcp_sport,
            )
            exp_pkt_to2 = testutils.simple_tcp_packet(
                eth_src=SWITCH_MAC,
                eth_dst=HOST2_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=HOST2_IPV4,
                ip_ttl=63,
                tcp_sport=test_tcp_sport,
            )
            exp_pkt_to3 = testutils.simple_tcp_packet(
                eth_src=SWITCH_MAC,
                eth_dst=HOST3_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=HOST2_IPV4,
                ip_ttl=63,
                tcp_sport=test_tcp_sport,
            )
            self.send_packet(self.port1, pkt_from1)
            out_port_index = self.verify_any_packet_any_port(
                [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
            )
            tcpsport_toport[out_port_index] = test_tcp_sport

        pkt_toport2 = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
            tcp_sport=tcpsport_toport[0],
        )
        pkt_toport3 = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
            tcp_sport=tcpsport_toport[1],
        )
        exp_pkt_to2 = testutils.simple_tcp_packet(
            eth_src=SWITCH_MAC,
            eth_dst=HOST2_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
            tcp_sport=tcpsport_toport[0],
        )
        exp_pkt_to3 = testutils.simple_tcp_packet(
            eth_src=SWITCH_MAC,
            eth_dst=HOST3_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
            tcp_sport=tcpsport_toport[1],
        )
        self.send_packet(self.port1, pkt_toport2)
        self.send_packet(self.port1, pkt_toport3)
        # In this assertion we are verifying:
        #  1) all ports of the same group are used almost once
        #  2) consistency of the forwarding decision, i.e. packets with the
        #     same 5-tuple fields are always forwarded out of the same port
        self.verify_each_packet_on_each_port(
            [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
        )


class FabricIPv4UnicastGroupTestAllPortTcpDport(FabricTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        # In this test we check that packets are forwarded to all ports when we
        # change one of the 5-tuple header values. In this case tcp-dst-port
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(HOST2_IPV4, 24, 300)
        grp_id = 66
        mbrs = [
            (self.port2, SWITCH_MAC, HOST2_MAC),
            (self.port3, SWITCH_MAC, HOST3_MAC),
        ]
        self.add_next_routing_group(300, grp_id, mbrs)
        self.set_egress_vlan(self.port2, vlan_id, False)
        self.set_egress_vlan(self.port3, vlan_id, False)
        # tcpdport_toport list is used to learn the tcp_destination_port that
        # causes the packet to be forwarded for each port
        tcpdport_toport = [None, None]
        for i in range(50):
            test_tcp_dport = 1230 + 3 * i
            pkt_from1 = testutils.simple_tcp_packet(
                eth_src=HOST1_MAC,
                eth_dst=SWITCH_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=HOST2_IPV4,
                ip_ttl=64,
                tcp_dport=test_tcp_dport,
            )
            exp_pkt_to2 = testutils.simple_tcp_packet(
                eth_src=SWITCH_MAC,
                eth_dst=HOST2_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=HOST2_IPV4,
                ip_ttl=63,
                tcp_dport=test_tcp_dport,
            )
            exp_pkt_to3 = testutils.simple_tcp_packet(
                eth_src=SWITCH_MAC,
                eth_dst=HOST3_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=HOST2_IPV4,
                ip_ttl=63,
                tcp_dport=test_tcp_dport,
            )
            self.send_packet(self.port1, pkt_from1)
            out_port_index = self.verify_any_packet_any_port(
                [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
            )
            tcpdport_toport[out_port_index] = test_tcp_dport

        pkt_toport2 = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
            tcp_dport=tcpdport_toport[0],
        )
        pkt_toport3 = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
            tcp_dport=tcpdport_toport[1],
        )
        exp_pkt_to2 = testutils.simple_tcp_packet(
            eth_src=SWITCH_MAC,
            eth_dst=HOST2_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
            tcp_dport=tcpdport_toport[0],
        )
        exp_pkt_to3 = testutils.simple_tcp_packet(
            eth_src=SWITCH_MAC,
            eth_dst=HOST3_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
            tcp_dport=tcpdport_toport[1],
        )
        self.send_packet(self.port1, pkt_toport2)
        self.send_packet(self.port1, pkt_toport3)
        # In this assertion we are verifying:
        #  1) all ports of the same group are used almost once
        #  2) consistency of the forwarding decision, i.e. packets with the
        #     same 5-tuple fields are always forwarded out of the same port
        self.verify_each_packet_on_each_port(
            [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
        )


class FabricIPv4UnicastGroupTestAllPortIpSrc(FabricTest):
    @tvsetup
    @autocleanup
    def IPv4UnicastGroupTestAllPortL4SrcIp(self, pkt_type):
        # In this test we check that packets are forwarded to all ports when we
        # change one of the 5-tuple header values and we have an ECMP-like
        # distribution.
        # In this case IP source for tcp and udp packets
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(HOST2_IPV4, 24, 300)
        grp_id = 66
        mbrs = [
            (self.port2, SWITCH_MAC, HOST2_MAC),
            (self.port3, SWITCH_MAC, HOST3_MAC),
        ]
        self.add_next_routing_group(300, grp_id, mbrs)
        self.set_egress_vlan(self.port2, vlan_id, False)
        self.set_egress_vlan(self.port3, vlan_id, False)
        # ipsource_toport list is used to learn the ip_src that causes the
        # packet to be forwarded for each port
        ipsource_toport = [None, None]
        for i in range(50):
            test_ipsource = "10.0.1." + str(i)
            pkt_from1 = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=HOST1_MAC,
                eth_dst=SWITCH_MAC,
                ip_src=test_ipsource,
                ip_dst=HOST2_IPV4,
                ip_ttl=64,
            )
            exp_pkt_to2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=SWITCH_MAC,
                eth_dst=HOST2_MAC,
                ip_src=test_ipsource,
                ip_dst=HOST2_IPV4,
                ip_ttl=63,
            )
            exp_pkt_to3 = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=SWITCH_MAC,
                eth_dst=HOST3_MAC,
                ip_src=test_ipsource,
                ip_dst=HOST2_IPV4,
                ip_ttl=63,
            )
            self.send_packet(self.port1, pkt_from1)
            out_port_index = self.verify_any_packet_any_port(
                [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
            )
            ipsource_toport[out_port_index] = test_ipsource

        pkt_toport2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=ipsource_toport[0],
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        pkt_toport3 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=ipsource_toport[1],
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        exp_pkt_to2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=SWITCH_MAC,
            eth_dst=HOST2_MAC,
            ip_src=ipsource_toport[0],
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
        )
        exp_pkt_to3 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=SWITCH_MAC,
            eth_dst=HOST3_MAC,
            ip_src=ipsource_toport[1],
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
        )
        self.send_packet(self.port1, pkt_toport2)
        self.send_packet(self.port1, pkt_toport3)
        # In this assertion we are verifying:
        #  1) all ports of the same group are used almost once
        #  2) consistency of the forwarding decision, i.e. packets with the
        #     same 5-tuple fields are always forwarded out of the same port
        self.verify_each_packet_on_each_port(
            [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
        )

    def runTest(self):
        self.IPv4UnicastGroupTestAllPortL4SrcIp("tcp")
        self.IPv4UnicastGroupTestAllPortL4SrcIp("udp")
        self.IPv4UnicastGroupTestAllPortL4SrcIp("icmp")


class FabricIPv4UnicastGroupTestAllPortIpDst(FabricTest):
    @tvsetup
    @autocleanup
    def IPv4UnicastGroupTestAllPortL4DstIp(self, pkt_type):
        # In this test we check that packets are forwarded to all ports when we
        # change one of the 5-tuple header values and we have an ECMP-like
        # distribution.
        # In this case IP dest for tcp and udp packets
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(HOST2_IPV4, 24, 300)
        grp_id = 66
        mbrs = [
            (self.port2, SWITCH_MAC, HOST2_MAC),
            (self.port3, SWITCH_MAC, HOST3_MAC),
        ]
        self.add_next_routing_group(300, grp_id, mbrs)
        self.set_egress_vlan(self.port2, vlan_id, False)
        self.set_egress_vlan(self.port3, vlan_id, False)
        # ipdst_toport list is used to learn the ip_dst that causes the packet
        # to be forwarded for each port
        ipdst_toport = [None, None]
        for i in range(50):
            # If we increment test_ipdst by 1 on hardware, all 50 packets hash
            # to the same ECMP group member and the test fails. Changing the
            # increment to 3 makes this not happen. This seems extremely
            # unlikely and needs further testing to confirm. A similar
            # situation seems to be happening with
            # FabricIPv4UnicastGroupTestAllPortTcpDport
            test_ipdst = "10.0.2." + str(3 * i)
            pkt_from1 = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=HOST1_MAC,
                eth_dst=SWITCH_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=test_ipdst,
                ip_ttl=64,
            )
            exp_pkt_to2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=SWITCH_MAC,
                eth_dst=HOST2_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=test_ipdst,
                ip_ttl=63,
            )
            exp_pkt_to3 = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=SWITCH_MAC,
                eth_dst=HOST3_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=test_ipdst,
                ip_ttl=63,
            )
            self.send_packet(self.port1, pkt_from1)
            out_port_index = self.verify_any_packet_any_port(
                [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
            )
            ipdst_toport[out_port_index] = test_ipdst

        pkt_toport2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=ipdst_toport[0],
            ip_ttl=64,
        )
        pkt_toport3 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=ipdst_toport[1],
            ip_ttl=64,
        )
        exp_pkt_to2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=SWITCH_MAC,
            eth_dst=HOST2_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=ipdst_toport[0],
            ip_ttl=63,
        )
        exp_pkt_to3 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=SWITCH_MAC,
            eth_dst=HOST3_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=ipdst_toport[1],
            ip_ttl=63,
        )
        self.send_packet(self.port1, pkt_toport2)
        self.send_packet(self.port1, pkt_toport3)
        # In this assertion we are verifying:
        #  1) all ports of the same group are used almost once
        #  2) consistency of the forwarding decision, i.e. packets with the
        #     same 5-tuple fields are always forwarded out of the same port
        self.verify_each_packet_on_each_port(
            [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
        )

    def runTest(self):
        self.IPv4UnicastGroupTestAllPortL4DstIp("tcp")
        self.IPv4UnicastGroupTestAllPortL4DstIp("udp")
        self.IPv4UnicastGroupTestAllPortL4DstIp("icmp")


class FabricIPv4MPLSTest(FabricTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(HOST2_IPV4, 24, 400)
        mpls_label = 0xABA
        self.add_next_mpls(400, mpls_label)
        self.add_next_routing(400, self.port2, SWITCH_MAC, HOST2_MAC)
        self.set_egress_vlan(self.port2, vlan_id, False)

        pkt_1to2 = testutils.simple_tcp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        exp_pkt_1to2 = testutils.simple_mpls_packet(
            eth_src=SWITCH_MAC,
            eth_dst=HOST2_MAC,
            mpls_tags=[{"label": mpls_label, "tc": 0, "s": 1, "ttl": DEFAULT_MPLS_TTL}],
            inner_frame=pkt_1to2[IP:],
        )

        self.send_packet(self.port1, pkt_1to2)
        self.verify_packets(exp_pkt_1to2, [self.port2])


class FabricIPv4MplsGroupTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, mac_dest, tagged1, tc_name):
        self.runIPv4UnicastTest(
            pkt,
            mac_dest,
            prefix_len=24,
            tagged1=tagged1,
            tagged2=False,
            is_next_hop_spine=True,
            port_type2=PORT_TYPE_INFRA,
        )

    def runTest(self):
        print("")
        for tagged1 in [True, False]:
            for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                tc_name = pkt_type + "_tagged_" + str(tagged1)
                print("Testing {} packet with tagged={}...".format(pkt_type, tagged1))
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    eth_src=HOST1_MAC,
                    eth_dst=SWITCH_MAC,
                    ip_src=HOST1_IPV4,
                    ip_dst=HOST2_IPV4,
                    pktlen=MIN_PKT_LEN,
                )
                self.doRunTest(pkt, HOST2_MAC, tagged1, tc_name=tc_name)


class FabricMplsSegmentRoutingTest(MplsSegmentRoutingTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, mac_dest, next_hop_spine, tc_name):
        self.runMplsSegmentRoutingTest(pkt, mac_dest, next_hop_spine)

    def runTest(self):
        print("")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
            for next_hop_spine in [True, False]:
                tc_name = pkt_type + "_next_hop_spine_" + str(next_hop_spine)
                print(
                    "Testing {} packet, next_hop_spine={}...".format(
                        pkt_type, next_hop_spine
                    )
                )
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    eth_src=HOST1_MAC,
                    eth_dst=SWITCH_MAC,
                    ip_src=HOST1_IPV4,
                    ip_dst=HOST2_IPV4,
                    pktlen=MIN_PKT_LEN,
                )
                self.doRunTest(pkt, HOST2_MAC, next_hop_spine, tc_name=tc_name)


class FabricIPv4MplsOverrideEdgeTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, mac_dest, tagged1, tc_name):
        if "tcp" in tc_name:
            ip_proto = IP_PROTO_TCP
        elif "udp" in tc_name:
            ip_proto = IP_PROTO_UDP
        elif "icmp" in tc_name:
            ip_proto = IP_PROTO_ICMP
        elif "sctp" in tc_name:
            ip_proto = IP_PROTO_SCTP

        self.set_egress_vlan(self.port3, DEFAULT_VLAN)
        self.add_next_routing(401, self.port3, SWITCH_MAC, HOST2_MAC)

        self.add_forwarding_acl_next(
            401,
            ig_port_type=PORT_TYPE_EDGE,
            ipv4_src=HOST1_IPV4,
            ipv4_dst=HOST2_IPV4,
            ip_proto=ip_proto,
        )
        self.runIPv4UnicastTest(
            pkt,
            mac_dest,
            prefix_len=24,
            tagged1=tagged1,
            tagged2=False,
            is_next_hop_spine=True,
            override_eg_port=self.port3,
            port_type2=PORT_TYPE_INFRA,
        )

    def runTest(self):
        print("")
        for tagged1 in [True, False]:
            for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                tc_name = pkt_type + "_tagged_" + str(tagged1)
                print("Testing {} packet with tagged={}...".format(pkt_type, tagged1))
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    eth_src=HOST1_MAC,
                    eth_dst=SWITCH_MAC,
                    ip_src=HOST1_IPV4,
                    ip_dst=HOST2_IPV4,
                    pktlen=MIN_PKT_LEN,
                )
                self.doRunTest(pkt, HOST2_MAC, tagged1, tc_name=tc_name)


class FabricIPv4MplsDoNotOverrideTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, mac_dest, tagged1, tc_name):
        self.set_egress_vlan(self.port3, DEFAULT_VLAN)
        self.add_next_routing(401, self.port3, SWITCH_MAC, HOST2_MAC)
        self.add_forwarding_acl_next(
            401, ig_port_type=PORT_TYPE_EDGE, ipv4_src=HOST3_IPV4, ipv4_dst=HOST4_IPV4
        )
        self.runIPv4UnicastTest(
            pkt,
            mac_dest,
            prefix_len=24,
            tagged1=tagged1,
            tagged2=False,
            is_next_hop_spine=True,
            port_type2=PORT_TYPE_INFRA,
        )

    def runTest(self):
        print("")
        for tagged1 in [True, False]:
            for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                tc_name = pkt_type + "_tagged_" + str(tagged1)
                print("Testing {} packet with tagged={}...".format(pkt_type, tagged1))
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    eth_src=HOST1_MAC,
                    eth_dst=SWITCH_MAC,
                    ip_src=HOST1_IPV4,
                    ip_dst=HOST2_IPV4,
                    pktlen=MIN_PKT_LEN,
                )
                self.doRunTest(pkt, HOST2_MAC, tagged1, tc_name=tc_name)


class FabricIPv4DoNotOverrideInfraTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt_type, mac_dest):
        if "tcp" == pkt_type:
            ip_proto = IP_PROTO_TCP
        elif "udp" == pkt_type:
            ip_proto = IP_PROTO_UDP
        elif "icmp" == pkt_type:
            ip_proto = IP_PROTO_ICMP
        elif "sctp" == pkt_type:
            ip_proto = IP_PROTO_SCTP
        elif pkt_type in GTP_PKT_TYPES:
            ip_proto = IP_PROTO_UDP
        self.set_ingress_port_vlan(
            self.port1, False, 0, DEFAULT_VLAN, port_type=PORT_TYPE_INFRA
        )
        self.set_forwarding_type(self.port1, SWITCH_MAC)
        self.add_forwarding_routing_v4_entry(HOST2_IPV4, 24, 400)
        self.add_next_vlan(400, VLAN_ID_1)
        self.add_next_routing(400, self.port2, SWITCH_MAC, HOST2_MAC)
        self.set_egress_vlan(self.port2, VLAN_ID_1, False)
        self.set_egress_vlan(self.port3, VLAN_ID_1, False)

        pkt_1to2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=SPINE_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )
        exp_pkt_1to2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=SWITCH_MAC,
            eth_dst=HOST2_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=63,
        )

        self.add_next_routing(401, self.port3, SWITCH_MAC, HOST2_MAC)
        self.add_forwarding_acl_next(
            401,
            ig_port_type=PORT_TYPE_EDGE,
            ipv4_src=HOST1_IPV4,
            ipv4_dst=HOST2_IPV4,
            ip_proto=ip_proto,
        )

        self.send_packet(self.port1, pkt_1to2)
        self.verify_packets(exp_pkt_1to2, [self.port2])
        self.verify_no_other_packets()

    def runTest(self):
        print("")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
            print("Testing {} packet...".format(pkt_type))
            self.doRunTest(pkt_type, HOST2_MAC)


class FabricIPv4UnicastGtpAclInnerDropTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        # Assert that GTP packets not meant to be forwarded by fabric-tna.p4 are
        # blocked using the inner IP+UDP headers by the ACL table.
        pkt = testutils.simple_udp_packet(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            udp_sport=5061,
            udp_dport=5060,
            pktlen=128,
        )
        pkt = pkt_add_gtp(
            pkt, out_ipv4_src=HOST3_IPV4, out_ipv4_dst=HOST4_IPV4, teid=0xEEFFC0F0
        )
        self.add_forwarding_acl_drop(
            ipv4_src=HOST1_IPV4,
            ipv4_dst=HOST2_IPV4,
            ip_proto=IP_PROTO_UDP,
            l4_sport=5061,
            l4_dport=5060,
        )
        self.runIPv4UnicastTest(pkt, next_hop_mac=HOST2_MAC, verify_pkt=False)


class FabricIPv4UnicastAclOuterDropTest(IPv4UnicastTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        # Assert that not encapsulated packets not meant to be forwarded by fabric-tna.p4
        # are blocked using the outer IP+UDP headers by the ACL table.
        pkt = (
            Ether(src=HOST1_MAC, dst=SWITCH_MAC)
            / IP(src=HOST1_IPV4, dst=HOST2_IPV4)
            / UDP(sport=5061, dport=5060)
            / ("\xab" * 128)
        )
        self.add_forwarding_acl_drop(
            ipv4_src=HOST1_IPV4,
            ipv4_dst=HOST2_IPV4,
            ip_proto=IP_PROTO_UDP,
            l4_sport=5061,
            l4_dport=5060,
        )
        self.runIPv4UnicastTest(pkt, next_hop_mac=HOST2_MAC, verify_pkt=False)


@group("packetio")
class FabricArpPacketOutTest(PacketOutTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_arp_packet(pktlen=MIN_PKT_LEN)
        self.runPacketOutTest(pkt)


@group("packetio")
class FabricShortIpPacketOutTest(PacketOutTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_ip_packet(pktlen=MIN_PKT_LEN)
        self.runPacketOutTest(pkt)


@group("packetio")
class FabricLongIpPacketOutTest(PacketOutTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_ip_packet(pktlen=160)
        self.runPacketOutTest(pkt)


@group("packetio")
class FabricArpPacketInTest(PacketInTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_arp_packet(pktlen=MIN_PKT_LEN)
        self.runPacketInTest(pkt, ETH_TYPE_ARP)


@group("packetio")
class FabricLongIpPacketInTest(PacketInTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_ip_packet(pktlen=160)
        self.runPacketInTest(pkt, ETH_TYPE_IPV4)


@group("packetio")
class FabricShortIpPacketInTest(PacketInTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_ip_packet(pktlen=MIN_PKT_LEN)
        self.runPacketInTest(pkt, ETH_TYPE_IPV4)


@group("packetio")
class FabricTaggedPacketInTest(PacketInTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_ip_packet(dl_vlan_enable=True, vlan_vid=10, pktlen=160)
        self.runPacketInTest(pkt, ETH_TYPE_IPV4, tagged=True, vlan_id=10)


@group("packetio")
class FabricDefaultVlanPacketInTest(FabricTest):
    @tvsetup
    @autocleanup
    def runTest(self):
        pkt = testutils.simple_eth_packet(pktlen=MIN_PKT_LEN)
        self.add_forwarding_acl_punt_to_cpu(eth_type=pkt[Ether].type)
        for port in [self.port1, self.port2]:
            self.send_packet(port, pkt)
            self.verify_packet_in(pkt, port)
        self.verify_no_other_packets()


@group("packetio")
@skipIf(is_v1model(), "Packet-in post ingress not supported for Bmv2.")
class FabricPacketInPostIngressTest(IPv4UnicastTest):
    """
    Packet-in generated using clone/punt_to_cpu_post_ingress actions should include changes
    from the ingress pipeline, while clone/punt_to_cpu action should not.
    """

    @tvsetup
    @autocleanup
    def doRunTest(self, action, post_ingress):
        add_acl_rule = getattr(self, f"add_forwarding_acl_{action}_to_cpu")
        add_acl_rule(eth_type=ETH_TYPE_IPV4, post_ingress=post_ingress)
        pkt = testutils.simple_udp_packet()
        self.runIPv4UnicastTest(
            pkt, next_hop_mac=HOST2_MAC, verify_pkt=(action == "copy")
        )

        # only "copy_to_cpu_post_ingress" action will include the change from next
        # control block, "punt_to_cpu_post_ingress" will skip the next control block
        # so the mac address will not be changed.
        if post_ingress and action == "copy":
            pkt = pkt_route(pkt, HOST2_MAC)

        self.verify_packet_in(pkt, self.port1)

    def runTest(self):
        print()
        for action in ["punt", "copy"]:
            for post_ingress in [False, True]:
                print(f"Testing action={action}, post_ingress={post_ingress}...")
                self.doRunTest(action, post_ingress)


class FabricGtpUnicastEcmpBasedOnTeid(FabricTest):
    """
    This test case verifies if the GTP encapsulated traffic
    is distributed over next hops by hashing on the TEID.
    """

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt_type):
        # In this test we check that packets are forwarded to all ports when we
        # change one of the values used for hash calculation and we have an ECMP-like
        # distribution.
        # In this case, we change TEID for GTP-encapsulated packets
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(S1U_SGW_IPV4, 24, 300)
        grp_id = 66
        mbrs = [
            (self.port2, SWITCH_MAC, HOST2_MAC),
            (self.port3, SWITCH_MAC, HOST3_MAC),
        ]
        self.add_next_routing_group(300, grp_id, mbrs)
        self.set_egress_vlan(self.port2, vlan_id, False)
        self.set_egress_vlan(self.port3, vlan_id, False)

        pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=HOST1_IPV4,
            ip_dst=HOST2_IPV4,
            ip_ttl=64,
        )

        # teid_toport list is used to learn the teid that causes the packet
        # to be forwarded for each port
        teid_toport = [None, None]
        for i in range(50):
            test_teid = i

            pkt_from1 = pkt_add_gtp(
                pkt,
                out_ipv4_src=S1U_ENB_IPV4,
                out_ipv4_dst=S1U_SGW_IPV4,
                teid=test_teid,
            )

            exp_pkt_to2 = pkt_from1.copy()
            exp_pkt_to2[Ether].src = SWITCH_MAC
            exp_pkt_to2[Ether].dst = HOST2_MAC
            exp_pkt_to2[IP].ttl = 63

            exp_pkt_to3 = pkt_from1.copy()
            exp_pkt_to3[Ether].src = SWITCH_MAC
            exp_pkt_to3[Ether].dst = HOST3_MAC
            exp_pkt_to3[IP].ttl = 63

            self.send_packet(self.port1, pkt_from1)
            out_port_index = self.verify_any_packet_any_port(
                [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
            )
            teid_toport[out_port_index] = test_teid

        pkt_toport2 = pkt_add_gtp(
            pkt,
            out_ipv4_src=S1U_ENB_IPV4,
            out_ipv4_dst=S1U_SGW_IPV4,
            teid=teid_toport[0],
        )

        pkt_toport3 = pkt_add_gtp(
            pkt,
            out_ipv4_src=S1U_ENB_IPV4,
            out_ipv4_dst=S1U_SGW_IPV4,
            teid=teid_toport[1],
        )

        exp_pkt_to2 = pkt_toport2.copy()
        exp_pkt_to2[Ether].src = SWITCH_MAC
        exp_pkt_to2[Ether].dst = HOST2_MAC
        exp_pkt_to2[IP].ttl = 63

        exp_pkt_to3 = pkt_toport3.copy()
        exp_pkt_to3[Ether].src = SWITCH_MAC
        exp_pkt_to3[Ether].dst = HOST3_MAC
        exp_pkt_to3[IP].ttl = 63

        self.send_packet(self.port1, pkt_toport2)
        self.send_packet(self.port1, pkt_toport3)
        # In this assertion we are verifying:
        #  1) all ports of the same group are used almost once
        #  2) consistency of the forwarding decision, i.e. packets with the
        #     same hashed fields are always forwarded out of the same port
        self.verify_each_packet_on_each_port(
            [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
        )

    def runTest(self):
        for pkt_type in BASE_PKT_TYPES:
            self.doRunTest(pkt_type)


@group("upf")
class FabricUpfCounterBypassTest(UpfSimpleTest):
    """
    This test case verifies that if we don't match on any UPF table, even if packets
    are allowed into the UPF pipeline, egress and ingress UPF counters are not
    incremented in the default index position.
    """

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, in_port, out_port, exp_pkt, upf_iface):
        self.setup_port(in_port, DEFAULT_VLAN, PORT_TYPE_EDGE)
        self.setup_port(out_port, DEFAULT_VLAN, PORT_TYPE_EDGE)
        # Allow packets into the UPF pipeline as if it comes from different interfaces
        if upf_iface == "N3":
            self.add_s1u_iface(pkt[IP].dst)
        elif upf_iface == "N6":
            self.add_ue_pool(pkt[IP].dst)
        elif upf_iface == "DBUF":
            self.add_dbuf_iface(pkt[IP].dst)
            if GTP_U_Header in exp_pkt:
                exp_pkt = pkt_remove_gtp(exp_pkt)
        # upf_iface == "NONE": do not configure UPF interfaces table
        self.add_forwarding_acl_set_output_port(out_port, ig_port=in_port)
        self.reset_upf_counters(DEFAULT_UPF_COUNTER_IDX)
        self.send_packet(in_port, pkt)
        self.verify_packet(exp_pkt, out_port)
        self.verify_upf_counters(DEFAULT_UPF_COUNTER_IDX, 0, 0, 0, 0)

    def runTest(self):
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
            for upf_iface in [None, "N3", "N6", "DBUF"]:
                if upf_iface is None:
                    log_str = "not allowed into UPF"
                else:
                    log_str = "allow into UPF as coming from: " + upf_iface
                print("Testing {}, {}...".format(pkt_type, log_str))
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    eth_src=HOST1_MAC,
                    eth_dst=SWITCH_MAC,
                    ip_src=HOST1_IPV4,
                    ip_dst=HOST2_IPV4,
                )
                self.doRunTest(pkt, self.port1, self.port2, pkt, upf_iface)


@group("upf")
class FabricUpfDownlinkEcmpTest(UpfSimpleTest):
    """
    This test case verifies if traffic from PDN to UEs (downlink) served by the same
    base station is distributed over next hops using GTP-aware load balancing.
    """

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt_type):
        vlan_id = 10
        self.set_ingress_port_vlan(self.port1, False, 0, vlan_id)
        self.set_forwarding_type(
            self.port1,
            SWITCH_MAC,
            ethertype=ETH_TYPE_IPV4,
            fwd_type=FORWARDING_TYPE_UNICAST_IPV4,
        )
        self.add_forwarding_routing_v4_entry(S1U_ENB_IPV4, 24, 300)
        grp_id = 66

        # used for this test only
        S1U_ENB_NEXTHOP1_MAC = "00:00:00:00:00:ee"
        S1U_ENB_NEXTHOP2_MAC = "00:00:00:00:00:ff"
        mbrs = [
            (self.port2, SWITCH_MAC, S1U_ENB_NEXTHOP1_MAC),
            (self.port3, SWITCH_MAC, S1U_ENB_NEXTHOP2_MAC),
        ]
        self.add_next_routing_group(300, grp_id, mbrs)
        self.set_egress_vlan(self.port2, vlan_id, False)
        self.set_egress_vlan(self.port3, vlan_id, False)

        self.add_gtp_tunnel_peer(
            tunnel_peer_id=S1U_ENB_TUNNEL_PEER_ID,
            tunnel_src_addr=S1U_SGW_IPV4,
            tunnel_dst_addr=S1U_ENB_IPV4,
        )

        # ue_ipv4_toport list is used to learn the ue_ipv4 address for a given packet.
        ue_ipv4_toport = [None, None]
        # teid_toport list is used to learn the teid
        # assigned by UPF for a downlink packet.
        teid_toport = [None, None]
        for i in range(50):
            ue_ipv4 = "10.0.0." + str(i)
            test_teid = i * 3

            self.setup_downlink(
                teid=test_teid,
                ue_addr=ue_ipv4,
                ctr_id=DOWNLINK_UPF_CTR_IDX,
                tunnel_peer_id=S1U_ENB_TUNNEL_PEER_ID,
            )

            pkt_from1 = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=HOST1_MAC,
                eth_dst=SWITCH_MAC,
                ip_src=UE2_IPV4,
                ip_dst=ue_ipv4,
                ip_ttl=64,
            )

            exp_pkt_to2 = pkt_from1.copy()
            exp_pkt_to2[IP].ttl = 63
            exp_pkt_to2 = pkt_add_gtp(
                exp_pkt_to2,
                out_ipv4_src=S1U_SGW_IPV4,
                out_ipv4_dst=S1U_ENB_IPV4,
                teid=test_teid,
            )
            exp_pkt_to2[Ether].src = SWITCH_MAC
            exp_pkt_to2[Ether].dst = S1U_ENB_NEXTHOP1_MAC

            exp_pkt_to3 = pkt_from1.copy()
            exp_pkt_to3[IP].ttl = 63
            exp_pkt_to3 = pkt_add_gtp(
                exp_pkt_to3,
                out_ipv4_src=S1U_SGW_IPV4,
                out_ipv4_dst=S1U_ENB_IPV4,
                teid=test_teid,
            )
            exp_pkt_to3[Ether].src = SWITCH_MAC
            exp_pkt_to3[Ether].dst = S1U_ENB_NEXTHOP2_MAC

            self.send_packet(self.port1, pkt_from1)
            out_port_index = self.verify_any_packet_any_port(
                [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
            )
            ue_ipv4_toport[out_port_index] = ue_ipv4
            teid_toport[out_port_index] = test_teid

        pkt_toport2 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=UE2_IPV4,
            ip_dst=ue_ipv4_toport[0],
            ip_ttl=64,
        )

        pkt_toport3 = getattr(testutils, "simple_%s_packet" % pkt_type)(
            eth_src=HOST1_MAC,
            eth_dst=SWITCH_MAC,
            ip_src=UE2_IPV4,
            ip_dst=ue_ipv4_toport[1],
            ip_ttl=64,
        )

        exp_pkt_to2 = pkt_toport2.copy()
        exp_pkt_to2[IP].ttl = 63
        exp_pkt_to2 = pkt_add_gtp(
            exp_pkt_to2,
            out_ipv4_src=S1U_SGW_IPV4,
            out_ipv4_dst=S1U_ENB_IPV4,
            teid=teid_toport[0],
        )
        exp_pkt_to2[Ether].src = SWITCH_MAC
        exp_pkt_to2[Ether].dst = S1U_ENB_NEXTHOP1_MAC

        exp_pkt_to3 = pkt_toport3.copy()
        exp_pkt_to3[IP].ttl = 63
        exp_pkt_to3 = pkt_add_gtp(
            exp_pkt_to3,
            out_ipv4_src=S1U_SGW_IPV4,
            out_ipv4_dst=S1U_ENB_IPV4,
            teid=teid_toport[1],
        )
        exp_pkt_to3[Ether].src = SWITCH_MAC
        exp_pkt_to3[Ether].dst = S1U_ENB_NEXTHOP2_MAC

        self.send_packet(self.port1, pkt_toport2)
        self.send_packet(self.port1, pkt_toport3)
        # In this assertion we are verifying:
        #  1) all ports of the same group are used almost once
        #  2) consistency of the forwarding decision, i.e. packets with the
        #     same 5-tuple fields are always forwarded out of the same port
        self.verify_each_packet_on_each_port(
            [exp_pkt_to2, exp_pkt_to3], [self.port2, self.port3]
        )

    def runTest(self):
        for pkt_type in BASE_PKT_TYPES:
            self.doRunTest(pkt_type)


@group("upf")
class FabricUpfDownlinkTest(UpfSimpleTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        pkt,
        tagged1,
        tagged2,
        with_psc,
        is_next_hop_spine,
        upf_app_filtering,
        **kwargs
    ):
        self.runDownlinkTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            with_psc=with_psc,
            is_next_hop_spine=is_next_hop_spine,
            app_filtering=upf_app_filtering,
        )

    def runTest(self):
        print("")
        pkt_addrs = {
            "eth_src": HOST1_MAC,
            "eth_dst": SWITCH_MAC,
            "ip_src": HOST1_IPV4,
            "ip_dst": UE1_IPV4,
        }
        for traffic_dir in ["host-leaf-host", "spine-leaf-host", "host-leaf-spine"]:
            for upf_app_filtering in [False, True]:
                for test_args in get_test_args(
                    traffic_dir=traffic_dir,
                    pkt_addrs=pkt_addrs,
                    upf_type="DL_PSC",
                    upf_app_filtering=upf_app_filtering,
                ):
                    self.doRunTest(**test_args)


@group("upf")
class FabricUpfUplinkTest(UpfSimpleTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        pkt,
        tagged1,
        tagged2,
        with_psc,
        is_next_hop_spine,
        upf_app_filtering,
        **kwargs
    ):
        self.runUplinkTest(
            ue_out_pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            with_psc=with_psc,
            is_next_hop_spine=is_next_hop_spine,
            app_filtering=upf_app_filtering,
        )

    def runTest(self):
        print("")
        pkt_addrs = {
            "eth_src": HOST1_MAC,
            "eth_dst": SWITCH_MAC,
            "ip_src": HOST1_IPV4,
            "ip_dst": HOST2_IPV4,
        }
        for traffic_dir in ["host-leaf-host", "host-leaf-spine", "spine-leaf-host"]:
            for upf_app_filtering in [False, True]:
                for test_args in get_test_args(
                    traffic_dir=traffic_dir,
                    pkt_addrs=pkt_addrs,
                    upf_type="UL_PSC",
                    upf_app_filtering=upf_app_filtering,
                ):
                    self.doRunTest(**test_args)


@group("upf")
class FabricUpfUplinkRecircTest(UpfSimpleTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self, pkt, allow_ue_recirculation, tagged1, tagged2, is_next_hop_spine, **kwargs
    ):
        self.runUplinkRecircTest(
            ue_out_pkt=pkt,
            allow=allow_ue_recirculation,
            tagged1=tagged1,
            tagged2=tagged2,
            is_next_hop_spine=is_next_hop_spine,
        )

    def runTest(self):
        print("")
        pkt_addrs = {
            "eth_src": HOST1_MAC,
            "eth_dst": SWITCH_MAC,
            "ip_src": UE1_IPV4,
            "ip_dst": UE2_IPV4,
        }
        for traffic_dir in ["host-leaf-host", "host-leaf-spine", "spine-leaf-host"]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir,
                pkt_addrs=pkt_addrs,
                upf_type="UL",
                ue_recirculation_test=True,
            ):
                self.doRunTest(**test_args)


@group("upf")
class FabricUpfDownlinkToDbufTest(UpfSimpleTest):
    """Tests downlink packets arriving from the PDN being routed to
    the dbuf device for buffering.
    """

    @tvsetup
    @autocleanup
    def doRunTest(
        self, pkt, tagged1, tagged2, is_next_hop_spine, is_dbuf_present, **kwargs
    ):
        self.runDownlinkToDbufTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            is_next_hop_spine=is_next_hop_spine,
            is_dbuf_present=is_dbuf_present,
        )

    def runTest(self):
        print("")
        pkt_addrs = {
            "eth_src": HOST1_MAC,
            "eth_dst": SWITCH_MAC,
            "ip_src": HOST1_IPV4,
            "ip_dst": UE1_IPV4,
        }
        for traffic_dir in ["host-leaf-host", "spine-leaf-host", "host-leaf-spine"]:
            for dbuf_present in [False, True]:
                for test_args in get_test_args(
                    traffic_dir=traffic_dir, pkt_addrs=pkt_addrs, upf_type="DL"
                ):
                    print("is_dbuf_present: " + str(dbuf_present))
                    self.doRunTest(**test_args, is_dbuf_present=dbuf_present)


@group("upf")
class FabricUpfDownlinkFromDbufTest(UpfSimpleTest):
    """Tests downlink packets being drained from the dbuf buffering device
    back into the switch to be tunneled to the enodeb.
    """

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, tagged1, tagged2, is_next_hop_spine, **kwargs):
        self.runDownlinkFromDbufTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            is_next_hop_spine=is_next_hop_spine,
        )

    def runTest(self):
        print("")
        pkt_addrs = {
            "eth_src": DBUF_MAC,
            "eth_dst": SWITCH_MAC,
            "ip_src": HOST1_IPV4,
            "ip_dst": UE1_IPV4,
        }
        for traffic_dir in ["host-leaf-host", "spine-leaf-host", "host-leaf-spine"]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, pkt_addrs=pkt_addrs, upf_type="DL"
            ):
                self.doRunTest(**test_args)


@group("int")
@group("upf")
class FabricUpfUplinkIntTest(UpfIntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        pkt_type,
        tagged1,
        tagged2,
        with_psc,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        **kwargs
    ):
        # Change the IP destination to ensure we are using differnt
        # flow for different test cases since the flow report filter
        # might disable the report.
        # TODO: Remove this part when we are able to reset the register
        # via P4Runtime.
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runUpfUplinkIntTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            with_psc=with_psc,
            is_next_hop_spine=is_next_hop_spine,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
        )

    def runTest(self):
        print("")
        for traffic_dir in [
            "host-leaf-host",
            "host-leaf-spine",
            "spine-leaf-host",
            "leaf-spine-leaf",
            "leaf-spine-spine",
        ]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, upf_type="UL_PSC", int_test_type="flow"
            ):
                self.doRunTest(**test_args)


@group("int")
@group("upf")
class FabricUpfDownlinkIntTest(UpfIntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        pkt_type,
        tagged1,
        tagged2,
        with_psc,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        **kwargs
    ):
        # Change the IP destination to ensure we are using differnt
        # flow for diffrent test cases since the flow report filter
        # might disable the report.
        # TODO: Remove this part when we are able to reset the register
        # via P4Runtime.
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runUpfDownlinkIntTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            with_psc=with_psc,
            is_next_hop_spine=is_next_hop_spine,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
        )

    def runTest(self):
        print("")
        for traffic_dir in [
            "host-leaf-host",
            "host-leaf-spine",
            "spine-leaf-host",
            "leaf-spine-leaf",
            "leaf-spine-spine",
        ]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, upf_type="DL_PSC", int_test_type="flow"
            ):
                self.doRunTest(**test_args)


# This test will assume the packet hits upf interface and miss the uplink UE Session table or
# the uplink Flows table
@group("int")
@group("upf")
class FabricUpfIntUplinkDropTest(UpfIntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        tagged1,
        tagged2,
        pkt_type,
        with_psc,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        drop_reason,
        **kwargs
    ):
        # Change the IP destination to ensure we are using different
        # flow for diffrent test cases since the flow report filter
        # might disable the report.
        # TODO: Remove this part when we are able to reset the register
        # via P4Runtime.
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runUplinkIntDropTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            with_psc=with_psc,
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=True,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
            drop_reason=drop_reason,
        )

    def runTest(self):
        print("")
        for traffic_dir in [
            "host-leaf-host",
            "host-leaf-spine",
            "spine-leaf-host",
            "leaf-spine-leaf",
            "leaf-spine-spine",
        ]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, upf_type="UL_PSC", int_test_type="eg_drop"
            ):
                self.doRunTest(**test_args)


# This test will assume the packet hits upf interface and miss the downlink UE Sessions table or
# the downlink Flows table
@group("int")
@group("upf")
class FabricUpfIntDownlinkDropTest(UpfIntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        tagged1,
        tagged2,
        pkt_type,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        drop_reason,
        **kwargs
    ):
        # Change the IP destination to ensure we are using differnt
        # flow for diffrent test cases since the flow report filter
        # might disable the report.
        # TODO: Remove this part when we are able to reset the register
        # via P4Runtime.
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runDownlinkIntDropTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=True,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
            drop_reason=drop_reason,
        )

    def runTest(self):
        print("")
        for traffic_dir in [
            "host-leaf-host",
            "host-leaf-spine",
            "leaf-spine-leaf",
            "leaf-spine-spine",
        ]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, upf_type="DL", int_test_type="eg_drop"
            ):
                self.doRunTest(**test_args)


@group("int")
class FabricIntFlowReportTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        tagged1,
        tagged2,
        pkt_type,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        **kwargs
    ):
        # Change the IP destination to ensure we are using differnt
        # flow for diffrent test cases since the flow report filter
        # might disable the report.
        # TODO: Remove this part when we are able to reset the register
        # via P4Runtime.
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runIntTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=True,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
        )

    def runTest(self):
        print("")
        for traffic_dir in [
            "host-leaf-host",
            "host-leaf-spine",
            "leaf-spine-leaf",
            "leaf-spine-spine",
        ]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, int_test_type="flow"
            ):
                self.doRunTest(**test_args)


@group("int")
class FabricIntIngressDropReportTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        tagged1,
        tagged2,
        pkt_type,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        drop_reason,
        **kwargs
    ):
        self.set_up_flow_report_filter_config(
            hop_latency_mask=0xF0000000, timestamp_mask=0xFFFFFFFF
        )
        # Change the IP destination to ensure we are using differnt
        # flow for diffrent test cases since the flow report filter
        # might disable the report.
        # TODO: Remove this part when we are able to reset the register
        # via P4Runtime.
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runIngressIntDropTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=True,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
            drop_reason=drop_reason,
        )

    def runTest(self):
        print("")
        # FIXME: Add INT_DROP_REASON_ROUTING_V4_MISS. Currently, there is an unknown bug
        #        which cause unexpected table(drop_report) miss.
        for traffic_dir in [
            "host-leaf-host",
            "host-leaf-spine",
            "leaf-spine-leaf",
            "leaf-spine-spine",
        ]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, int_test_type="ig_drop"
            ):
                self.doRunTest(**test_args)


@group("int")
class FabricIntEgressDropReportTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        tagged1,
        tagged2,
        pkt_type,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        **kwargs
    ):
        self.set_up_flow_report_filter_config(
            hop_latency_mask=0xF0000000, timestamp_mask=0xFFFFFFFF
        )
        # Change the IP destination to ensure we are using differnt
        # flow for diffrent test cases since the flow report filter
        # might disable the report.
        # TODO: Remove this part when we are able to reset the register
        # via P4Runtime.
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runEgressIntDropTest(
            pkt=pkt,
            tagged1=tagged1,
            tagged2=tagged2,
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=True,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
            drop_reason=INT_DROP_REASON_EGRESS_NEXT_MISS,
        )

    def runTest(self):
        print("")
        for traffic_dir in [
            "host-leaf-host",
            "host-leaf-spine",
            "leaf-spine-leaf",
            "leaf-spine-spine",
        ]:
            for test_args in get_test_args(
                traffic_dir=traffic_dir, int_test_type="flow"
            ):
                self.doRunTest(**test_args)


@group("int")
@skipIf(is_v1model(), "Flow report filter not implemented for v1model.")
class FabricFlowReportFilterNoChangeTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self, vlan_conf, tagged, pkt_type, is_next_hop_spine, expect_int_report, ip_dst,
    ):
        self.set_up_flow_report_filter_config(
            hop_latency_mask=0xF0000000, timestamp_mask=0
        )
        print(
            "Testing VLAN={}, pkt={}, is_next_hop_spine={}...".format(
                vlan_conf, pkt_type, is_next_hop_spine
            )
        )
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(ip_dst=ip_dst)
        self.runIntTest(
            pkt=pkt,
            tagged1=tagged[0],
            tagged2=tagged[1],
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=expect_int_report,
            is_device_spine=False,
            send_report_to_spine=False,
        )

    def runTest(self):
        print("")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES | VXLAN_PKT_TYPES:
            expect_int_report = True
            # Change the IP destination to ensure we are using differnt
            # flow for diffrent test cases since the flow report filter
            # might disable the report.
            # TODO: Remove this part when we are able to reset the register
            # via P4Runtime.
            ip_dst = self.get_single_use_ip()
            for vlan_conf, tagged in vlan_confs.items():
                for is_next_hop_spine in [False, True]:
                    if is_next_hop_spine and tagged[1]:
                        continue
                    self.doRunTest(
                        vlan_conf,
                        tagged,
                        pkt_type,
                        is_next_hop_spine,
                        expect_int_report,
                        ip_dst,
                    )

                    # We should expect not receiving any report after the first
                    # report since packet uses 5-tuple as flow ID.
                    expect_int_report = False


@group("int")
@skipIf(is_v1model(), "Flow report filter not implemented for v1model.")
class FabricFlowReportFilterChangeTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, ig_port, eg_port, expect_int_report, ip_src, ip_dst):
        self.set_up_flow_report_filter_config(
            hop_latency_mask=0xF0000000, timestamp_mask=0
        )
        print(
            "Testing ig_port={}, eg_port={}, expect_int_report={}...".format(
                ig_port, eg_port, expect_int_report
            )
        )
        pkt = testutils.simple_tcp_packet()
        pkt[IP].src = ip_src
        pkt[IP].dst = ip_dst
        self.runIntTest(
            pkt=pkt,
            tagged1=None,
            tagged2=None,
            is_next_hop_spine=False,
            ig_port=ig_port,
            eg_port=eg_port,
            expect_int_report=expect_int_report,
            is_device_spine=False,
            send_report_to_spine=False,
        )

    def runTest(self):
        print("")
        # Test with ingress port changed.
        ingress_port_test_profiles = [
            (self.port1, self.port2, True),  # ig port, eg port, receive report
            (self.port1, self.port2, False),
            (self.port4, self.port2, True),
        ]
        ip_src = self.get_single_use_ip()
        ip_dst = self.get_single_use_ip()
        for ig_port, eg_port, expect_int_report in ingress_port_test_profiles:
            self.doRunTest(
                ig_port=ig_port,
                eg_port=eg_port,
                ip_src=ip_src,
                ip_dst=ip_dst,
                expect_int_report=expect_int_report,
            )
        # Test with egress port changed.
        egress_port_test_profiles = [
            (self.port1, self.port2, True),  # ig port, eg port, receive report
            (self.port1, self.port2, False),
            (self.port1, self.port4, True),
        ]
        ip_src = self.get_single_use_ip()
        ip_dst = self.get_single_use_ip()
        for ig_port, eg_port, expect_int_report in egress_port_test_profiles:
            self.doRunTest(
                ig_port=ig_port,
                eg_port=eg_port,
                ip_src=ip_src,
                ip_dst=ip_dst,
                expect_int_report=expect_int_report,
            )


@group("int")
@skipIf(is_v1model(), "Drop report filter not implemented for v1model.")
class FabricDropReportFilterTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self, vlan_conf, tagged, pkt_type, is_next_hop_spine, expect_int_report, ip_dst,
    ):
        self.set_up_flow_report_filter_config(
            hop_latency_mask=0xF0000000, timestamp_mask=0
        )
        print(
            "Testing VLAN={}, pkt={}, is_next_hop_spine={}...".format(
                vlan_conf, pkt_type, is_next_hop_spine
            )
        )
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(ip_dst=ip_dst)
        self.runIngressIntDropTest(
            pkt=pkt,
            tagged1=tagged[0],
            tagged2=tagged[1],
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=expect_int_report,
            is_device_spine=False,
            send_report_to_spine=False,
            drop_reason=INT_DROP_REASON_ACL_DENY,
        )

    def runTest(self):
        print("")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES | VXLAN_PKT_TYPES:
            expect_int_report = True
            # Change the IP destination to ensure we are using differnt
            # flow for diffrent test cases since the flow report filter
            # might disable the report.
            # TODO: Remove this part when we are able to reset the register
            # via P4Runtime.
            ip_dst = self.get_single_use_ip()
            for vlan_conf, tagged in vlan_confs.items():
                for is_next_hop_spine in [False, True]:
                    if is_next_hop_spine and tagged[1]:
                        continue
                    self.doRunTest(
                        vlan_conf,
                        tagged,
                        pkt_type,
                        is_next_hop_spine,
                        expect_int_report,
                        ip_dst,
                    )

                    # We should expect not receiving any report after the first
                    # report since packet uses 5-tuple as flow ID.
                    expect_int_report = False


@group("int")
@skipIf(is_v1model(), "Queue report not implemented for v1model.")
class FabricIntQueueReportTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self,
        vlan_conf,
        tagged,
        pkt_type,
        is_next_hop_spine,
        is_device_spine,
        send_report_to_spine,
        watch_flow,
    ):
        print(
            f"Testing VLAN={vlan_conf}, pkt={pkt_type}, is_next_hop_spine={is_next_hop_spine}, "
            f"is_device_spine={is_device_spine}, send_report_to_spine={send_report_to_spine}, "
            f"watch_flow={watch_flow}..."
        )
        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
            ip_dst=self.get_single_use_ip()
        )
        self.runIntQueueTest(
            pkt=pkt,
            tagged1=tagged[0],
            tagged2=tagged[1],
            is_next_hop_spine=is_next_hop_spine,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=True,
            is_device_spine=is_device_spine,
            send_report_to_spine=send_report_to_spine,
            watch_flow=watch_flow,
        )

    def runTest(self):
        print("")
        for is_device_spine in [False, True]:
            for vlan_conf, tagged in vlan_confs.items():
                if is_device_spine and (tagged[0] or tagged[1]):
                    continue
                for is_next_hop_spine in [False, True]:
                    if is_next_hop_spine and tagged[1]:
                        continue
                    for send_report_to_spine in [False, True]:
                        if send_report_to_spine and tagged[1]:
                            continue
                        for pkt_type in (
                            BASE_PKT_TYPES | GTP_PKT_TYPES | VXLAN_PKT_TYPES
                        ):
                            for watch_flow in [False, True]:
                                self.doRunTest(
                                    vlan_conf,
                                    tagged,
                                    pkt_type,
                                    is_next_hop_spine,
                                    is_device_spine,
                                    send_report_to_spine,
                                    watch_flow,
                                )


@group("int")
@skipIf(is_v1model(), "Queue reports not implemented for v1model.")
# Skip HW PTF test
# We cannot verify value from the register which not belong to pipe 0 since the current
# P4Runtime and Stratum only allows us to read register from pipe 0.
@group("no-hw")
class FabricIntQueueReportQuotaTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(
        self, expect_int_report, quota_left, threshold_trigger, threshold_reset,
    ):
        print(
            f"Testing expect_int_report={expect_int_report}, quota_left={quota_left}, "
            f"threshold_trigger={threshold_trigger}, threshold_reset={threshold_reset}..."
        )
        pkt = testutils.simple_udp_packet()
        self.runIntQueueTest(
            pkt=pkt,
            tagged1=False,
            tagged2=False,
            is_next_hop_spine=False,
            ig_port=self.port1,
            eg_port=self.port2,
            expect_int_report=expect_int_report,
            is_device_spine=False,
            send_report_to_spine=False,
            watch_flow=False,
            reset_quota=False,
            threshold_trigger=threshold_trigger,
            threshold_reset=threshold_reset,
        )
        self.verify_quota(
            port=self.sdn_to_sdk_port[self.port2], qid=0, quota=quota_left
        )

    def runTest(self):
        print("")
        # Initialize the queue report quota for output port and queue to just 1
        # After that, configure the threshold to a small value and send a packet to the
        # device to trigger queue report. We should expect to receive an INT queue
        # report and the quota should become zero.
        self.set_queue_report_quota(
            port=self.sdn_to_sdk_port[self.port2], qid=0, quota=1
        )
        self.doRunTest(
            expect_int_report=True,
            quota_left=0,
            threshold_trigger=10,
            threshold_reset=0,
        )
        # Send another packet, since the quota is now zero, the pipeline should not
        # send any INT queue report.
        self.doRunTest(
            expect_int_report=False,
            quota_left=0,
            threshold_trigger=10,
            threshold_reset=0,
        )
        # Make the trigger threshold higher than the latency, but the reset threshold lower.
        # The switch should not reset the quota nor generate a report.
        self.doRunTest(
            expect_int_report=False,
            quota_left=0,
            threshold_trigger=0xFFFFFFFF,
            threshold_reset=0,
        )
        # Set the reset threshold very high to make sure the packet latency will cause the quota to
        # reset (to a default value hardcoded in the P4 program). There should be no report from the
        # switch since the quota reset action shouldn't generate any.
        self.doRunTest(
            expect_int_report=False,
            quota_left=INT_DEFAULT_QUEUE_REPORT_QUOTA,
            threshold_trigger=0xFFFFFFFF,
            threshold_reset=0xFFFFFFFF,
        )
        # Finally, configure the trigger threshold to a low value. We should receive a report since the
        # quota has been reset.
        self.doRunTest(
            expect_int_report=True,
            quota_left=INT_DEFAULT_QUEUE_REPORT_QUOTA - 1,
            threshold_trigger=10,
            threshold_reset=0,
        )


@group("bng")
class FabricPppoeUpstreamTest(PppoeTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, tagged2, is_next_hop_spine, line_enabled):
        self.runUpstreamV4Test(pkt, tagged2, is_next_hop_spine, line_enabled)

    def runTest(self):
        print("")
        for line_enabled in [True, False]:
            for out_tagged in [False, True]:
                for is_next_hop_spine in [False, True]:
                    if is_next_hop_spine and out_tagged:
                        continue
                    for pkt_type in BASE_PKT_TYPES:
                        print(
                            "Testing {} packet, line_enabled={}, out_tagged={}, is_next_hop_spine={} ...".format(
                                pkt_type, line_enabled, out_tagged, is_next_hop_spine
                            )
                        )
                        pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
                            pktlen=120
                        )
                        self.doRunTest(pkt, out_tagged, is_next_hop_spine, line_enabled)


@group("bng")
class FabricPppoeControlPacketInTest(PppoeTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, line_mapped):
        self.runControlPacketInTest(pkt, line_mapped)

    def runTest(self):
        # FIXME: using a dummy payload will generate malformed PPP packets,
        #  instead we should use appropriate PPP protocol values and PPPoED
        #  payload (tags)
        # https://www.cloudshark.org/captures/f79aea31ad53
        pkts = {
            "PADI": Ether(src=HOST1_MAC, dst=BROADCAST_MAC)
            / PPPoED(version=1, type=1, code=PPPOED_CODE_PADI)
            / "dummy pppoed payload",
            "PADR": Ether(src=HOST1_MAC, dst=SWITCH_MAC)
            / PPPoED(version=1, type=1, code=PPPOED_CODE_PADR)
            / "dummy pppoed payload",
        }

        print("")
        for line_mapped in [True, False]:
            for pkt_type, pkt in pkts.items():
                print(
                    "Testing {} packet, line_mapped={}...".format(pkt_type, line_mapped)
                )
                self.doRunTest(pkt, line_mapped)


@group("bng")
class FabricPppoeControlPacketOutTest(PppoeTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt):
        self.runControlPacketOutTest(pkt)

    def runTest(self):
        # FIXME: using a dummy payload will generate malformed PPP packets,
        #  instead we should use appropriate PPP protocol values and PPPoED
        #  payload (tags)
        # https://www.cloudshark.org/captures/f79aea31ad53
        pkts = {
            "PADO": Ether(src=SWITCH_MAC, dst=HOST1_MAC)
            / PPPoED(version=1, type=1, code=PPPOED_CODE_PADO)
            / "dummy pppoed payload",
            "PADS": Ether(src=SWITCH_MAC, dst=HOST1_MAC)
            / PPPoED(version=1, type=1, code=PPPOED_CODE_PADS)
            / "dummy pppoed payload",
        }

        print("")
        for pkt_type, pkt in pkts.items():
            print("Testing {} packet...".format(pkt_type))
            self.doRunTest(pkt)


@group("bng")
class FabricPppoeDownstreamTest(PppoeTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, in_tagged, line_enabled):
        self.runDownstreamV4Test(pkt, in_tagged, line_enabled)

    def runTest(self):
        print("")
        for line_enabled in [True, False]:
            for in_tagged in [False, True]:
                for pkt_type in BASE_PKT_TYPES:
                    print(
                        "Testing {} packet, line_enabled={}, "
                        "in_tagged={}...".format(pkt_type, line_enabled, in_tagged)
                    )
                    pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
                        pktlen=120
                    )
                    self.doRunTest(pkt, in_tagged, line_enabled)


@group("dth")
class FabricDoubleTaggedHostUpstream(DoubleVlanTerminationTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, out_tagged, is_next_hop_spine):
        self.runPopAndRouteTest(
            pkt,
            next_hop_mac=HOST2_MAC,
            vlan_id=VLAN_ID_1,
            inner_vlan_id=VLAN_ID_2,
            out_tagged=out_tagged,
            is_next_hop_spine=is_next_hop_spine,
        )

    def runTest(self):
        print("")
        for out_tagged in [True, False]:
            for is_next_hop_spine in [True, False]:
                if is_next_hop_spine and out_tagged:
                    continue
                for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                    print(
                        "Testing {} packet, out_tagged={}...".format(
                            pkt_type, out_tagged
                        )
                    )
                    pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
                        pktlen=120
                    )
                    self.doRunTest(pkt, out_tagged, is_next_hop_spine)


@group("dth")
class FabricDoubleTaggedHostDownstream(DoubleVlanTerminationTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, in_tagged):
        self.runRouteAndPushTest(
            pkt,
            next_hop_mac=HOST2_MAC,
            next_vlan_id=VLAN_ID_1,
            next_inner_vlan_id=VLAN_ID_2,
            in_tagged=in_tagged,
        )

    def runTest(self):
        print("")
        for in_tagged in [True, False]:
            for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
                print("Testing {} packet, in_tagged={}...".format(pkt_type, in_tagged))
                pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
                    pktlen=120
                )
                self.doRunTest(pkt, in_tagged)


@group("p4rt")
class TableEntryReadWriteTest(FabricTest):
    @tvsetup
    @autocleanup
    def doRunTest(self):
        req, _ = self.add_bridging_entry(1, "00:00:00:00:00:01", "ff:ff:ff:ff:ff:ff", 1)
        expected_bridging_entry = req.updates[0].entity.table_entry
        received_bridging_entry = self.read_bridging_entry(
            1, "00:00:00:00:00:01", "ff:ff:ff:ff:ff:ff"
        )
        self.verify_p4runtime_entity(expected_bridging_entry, received_bridging_entry)

        req, _ = self.add_forwarding_acl_punt_to_cpu(ETH_TYPE_IPV4)
        expected_acl_entry = req.updates[0].entity.table_entry
        received_acl_entry = self.read_forwarding_acl_punt_to_cpu(ETH_TYPE_IPV4)
        self.verify_p4runtime_entity(expected_acl_entry, received_acl_entry)

        req, _ = self.add_forwarding_acl_set_output_port(self.port2, ig_port=self.port1)
        expected_acl_entry = req.updates[0].entity.table_entry
        received_acl_entry = self.read_forwarding_acl_set_output_port(
            ig_port=self.port1
        )
        self.verify_p4runtime_entity(expected_acl_entry, received_acl_entry)

    def runTest(self):
        print("")
        self.doRunTest()


@group("p4rt")
class ActionProfileMemberReadWriteTest(FabricTest):
    @tvsetup
    @autocleanup
    def doRunTest(self):
        req, _ = self.add_next_hashed_group_member(
            "output_hashed", [("port_num", stringify(self.port1, PORT_SIZE_BYTES))]
        )
        expected_action_profile_member = req.updates[0].entity.action_profile_member
        mbr_id = expected_action_profile_member.member_id
        received_action_profile_member = self.read_next_hashed_group_member(mbr_id)
        self.verify_p4runtime_entity(
            expected_action_profile_member, received_action_profile_member
        )

    def runTest(self):
        print("")
        self.doRunTest()


@group("p4rt")
class ActionProfileGroupReadWriteTest(FabricTest):
    @tvsetup
    @autocleanup
    def doRunTest(self):
        req, _ = self.add_next_hashed_group_member(
            "output_hashed", [("port_num", stringify(self.port1, PORT_SIZE_BYTES))]
        )
        member_installed = req.updates[0].entity.action_profile_member
        mbr_id = member_installed.member_id

        grp_id = 1
        req, _ = self.add_next_hashed_group(grp_id, [mbr_id])
        expected_action_profile_group = req.updates[0].entity.action_profile_group
        self.verify_next_hashed_group(grp_id, expected_action_profile_group)

    def runTest(self):
        print("")
        self.doRunTest()


@group("p4rt")
class ActionProfileGroupModificationTest(FabricTest):
    @tvsetup
    @autocleanup
    def doRunTest(self):
        # Insert members
        mbr_ids = []
        for port_num in range(1, 4):
            req, _ = self.add_next_hashed_group_member(
                "output_hashed", [("port_num", stringify(port_num, PORT_SIZE_BYTES))]
            )
            member_installed = req.updates[0].entity.action_profile_member
            mbr_ids.append(member_installed.member_id)

        # Insert group with member-1 and member-2
        grp_id = 1
        req, _ = self.add_next_hashed_group(grp_id, mbr_ids[:2])
        expected_action_profile_group = req.updates[0].entity.action_profile_group
        received_action_profile_group = self.read_next_hashed_group(grp_id)
        self.verify_p4runtime_entity(
            expected_action_profile_group, received_action_profile_group
        )

        # Modify group with member-2 and member-3
        req, _ = self.modify_next_hashed_group(grp_id, mbr_ids[1:], grp_size=2)
        expected_action_profile_group = req.updates[0].entity.action_profile_group
        received_action_profile_group = self.read_next_hashed_group(grp_id)
        self.verify_p4runtime_entity(
            expected_action_profile_group, received_action_profile_group
        )

    def runTest(self):
        print("")
        self.doRunTest()


@group("p4rt")
class MulticastGroupReadWriteTest(FabricTest):
    @tvsetup
    @autocleanup
    def doRunTest(self):
        grp_id = 10
        # (instance, port)
        replicas = [(0, self.port1), (0, self.port2), (0, self.port3)]
        req, _ = self.add_mcast_group(grp_id, replicas)
        expected_mc_entry = req.updates[
            0
        ].entity.packet_replication_engine_entry.multicast_group_entry
        self.verify_mcast_group(grp_id, expected_mc_entry)

    def runTest(self):
        print("")
        self.doRunTest()


@group("p4rt")
class MulticastGroupModificationTest(FabricTest):

    # Not using the auto cleanup since the Stratum modifies the
    # multicast node table internally
    @tvsetup
    def doRunTest(self):
        # Add group with egress port 1~3 (instance 1 and 2)
        grp_id = 10
        # (instance, port)
        replicas = [
            (1, self.port1),
            (1, self.port2),
            (1, self.port3),
            (2, self.port1),
            (2, self.port2),
            (2, self.port3),
        ]
        self.add_mcast_group(grp_id, replicas)

        # Modify the group with egress port 2~4 (instance 2 and 3)
        # (instance, port)
        replicas = [(2, 2), (2, 3), (2, 4), (3, 2), (3, 3), (3, 4)]
        req, _ = self.modify_mcast_group(grp_id, replicas)
        expected_mc_entry = req.updates[
            0
        ].entity.packet_replication_engine_entry.multicast_group_entry
        self.verify_mcast_group(grp_id, expected_mc_entry)

        # Cleanup
        self.delete_mcast_group(grp_id)

    def runTest(self):
        print("")
        self.doRunTest()


@group("p4rt")
class CounterTest(BridgingTest):
    @tvsetup
    @autocleanup
    def doRunTest(self):
        pkt = getattr(testutils, "simple_tcp_packet")(pktlen=120)
        self.runBridgingTest(False, False, pkt)
        # Check direct counters from 'ingress_port_vlan' table
        table_entries = [
            req.updates[0].entity.table_entry
            for req in self.reqs
            if req.updates[0].entity.HasField("table_entry")
        ]
        ingress_port_vlan_tid = self.get_table_id("ingress_port_vlan")
        table_entries = [
            te for te in table_entries if te.table_id == ingress_port_vlan_tid
        ]

        # Here, both table entries hits once with a
        # simple TCP packet(120 bytes + 2*2 bytes checksum inserted by scapy)
        for table_entry in table_entries:
            self.verify_direct_counter(table_entry, 124, 1)

        # Check that direct counters can be set/cleared.
        for table_entry in table_entries:
            self.write_direct_counter(table_entry, 0, 0)
            self.verify_direct_counter(table_entry, 0, 0)

            self.write_direct_counter(table_entry, 1024, 1024)
            self.verify_direct_counter(table_entry, 1024, 1024)

        try:
            self.get_counter("fwd_type_counter")
        except Exception:
            print("Unable to find indirect counter `fwd_type_counter`, skip")
            return

        # Read indirect counter (fwd_type_counter)
        # Here we are trying to read counter for traffic class "0"
        # which means how many traffic for bridging
        # In the bridging test we sent two TCP packets and both packets
        # are classified as bridging class.
        self.verify_indirect_counter("fwd_type_counter", 0, "BOTH", 248, 2)

    def runTest(self):
        print("")
        self.doRunTest()


# Disable the loopback mode test since we are going to use Stratum main.p4 for CCP instead of fabric-tna
# and we will remove loopback mode from fabric-tna once we move all CCP tests to main.p4.
@skip("Deprecated")
class FabricIpv4UnicastLoopbackModeTest(IPv4UnicastTest):
    """Emulates TV loopback mode for Ipv4UnicastTest"""

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, next_hop_mac):
        # Since we cannot put interfaces in loopback mode, verify that output
        # packet has fake ether type for loopback...
        self.runIPv4UnicastTest(
            pkt, next_hop_mac=next_hop_mac, prefix_len=24, no_send=True
        )
        exp_pkt_1 = (
            Ether(type=ETH_TYPE_CPU_LOOPBACK_INGRESS, src=ZERO_MAC, dst=ZERO_MAC) / pkt
        )
        routed_pkt = pkt_decrement_ttl(pkt_route(pkt, next_hop_mac))
        exp_pkt_2 = (
            Ether(type=ETH_TYPE_CPU_LOOPBACK_EGRESS, src=ZERO_MAC, dst=ZERO_MAC)
            / routed_pkt
        )
        self.send_packet_out(
            self.build_packet_out(
                pkt, self.port1, cpu_loopback_mode=CPU_LOOPBACK_MODE_INGRESS
            )
        )
        self.verify_packet(exp_pkt_1, self.port1)
        self.send_packet(self.port1, exp_pkt_1)
        self.verify_packet(exp_pkt_2, self.port2)
        self.send_packet(self.port2, exp_pkt_2)
        self.verify_packet_in(routed_pkt, self.port2)
        self.verify_no_other_packets()

    def runTest(self):
        print("")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES:
            print("Testing {} packet...".format(pkt_type))
            pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                eth_src=HOST1_MAC,
                eth_dst=SWITCH_MAC,
                ip_src=HOST1_IPV4,
                ip_dst=HOST2_IPV4,
                pktlen=MIN_PKT_LEN,
            )
            self.doRunTest(pkt, HOST2_MAC)


# Disable the loopback mode test since we are going to use Stratum main.p4 for CCP instead of fabric-tna
# and we will remove loopback mode from fabric-tna once we move all CCP tests to main.p4.
@skip("Deprecated")
class FabricPacketInLoopbackModeTest(FabricTest):
    """Emulates TV loopback mode for packet-in tests"""

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, tagged):
        self.add_forwarding_acl_punt_to_cpu(eth_type=pkt[Ether].type)
        if tagged:
            pkt = pkt_add_vlan(pkt, VLAN_ID_1)
        exp_pkt_1 = (
            Ether(type=ETH_TYPE_CPU_LOOPBACK_INGRESS, src=ZERO_MAC, dst=ZERO_MAC) / pkt
        )
        for port in [self.port1, self.port2]:
            if tagged:
                self.set_ingress_port_vlan(port, True, VLAN_ID_1, VLAN_ID_1)
            else:
                self.set_ingress_port_vlan(port, False, 0, VLAN_ID_1)
            self.send_packet_out(
                self.build_packet_out(
                    pkt, port, cpu_loopback_mode=CPU_LOOPBACK_MODE_INGRESS
                )
            )
            self.verify_packet(exp_pkt_1, port)
            self.send_packet(port, exp_pkt_1)
            self.verify_packet_in(pkt, port)
        self.verify_no_other_packets()

    def runTest(self):
        print("")
        for pkt_type in ["tcp", "udp", "icmp", "arp"]:
            for tagged in [True, False]:
                print("Testing {} packet, tagged={}...".format(pkt_type, tagged))
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    pktlen=MIN_PKT_LEN
                )
                self.doRunTest(pkt, tagged)


# Disable the loopback mode test since we are going to use Stratum main.p4 for CCP instead of fabric-tna
# and we will remove loopback mode from fabric-tna once we move all CCP tests to main.p4.
@skip("Deprecated")
class FabricPacketOutLoopbackModeTest(FabricTest):
    """Emulates TV loopback mode for packet-out tests"""

    @tvsetup
    @autocleanup
    def doRunTest(self, pkt):
        exp_pkt_1 = (
            Ether(type=ETH_TYPE_CPU_LOOPBACK_EGRESS, src=ZERO_MAC, dst=ZERO_MAC) / pkt
        )
        for port in [self.port1, self.port2]:
            self.send_packet_out(
                self.build_packet_out(
                    pkt, port, cpu_loopback_mode=CPU_LOOPBACK_MODE_DIRECT
                )
            )
            self.verify_packet(exp_pkt_1, port)
            self.send_packet(port, exp_pkt_1)
            self.verify_packet_in(pkt, port)
        self.verify_no_other_packets()

    def runTest(self):
        print("")
        for pkt_type in ["tcp", "udp", "icmp", "arp"]:
            print("Testing {} packet...".format(pkt_type))
            pkt = getattr(testutils, "simple_{}_packet".format(pkt_type))(
                pktlen=MIN_PKT_LEN
            )
            self.doRunTest(pkt)


# Disable the loopback mode test since we are going to use Stratum main.p4 for CCP instead of fabric-tna
# and we will remove loopback mode from fabric-tna once we move all CCP tests to main.p4.
@group("int")
@skip("Deprecated")
class FabricIntFlowReportLoopbackModeTest(IntTest):
    @tvsetup
    @autocleanup
    def doRunTest(self, pkt, next_hop_mac, is_device_spine, send_report_to_spine=False):

        # Set collector, report table, and mirror sessions
        self.set_up_int_flows(is_device_spine, pkt, send_report_to_spine)

        self.runIPv4UnicastTest(
            pkt, next_hop_mac=next_hop_mac, prefix_len=24, no_send=True
        )

        exp_pkt_1 = (
            Ether(type=ETH_TYPE_CPU_LOOPBACK_INGRESS, src=ZERO_MAC, dst=ZERO_MAC) / pkt
        )
        routed_pkt = pkt_decrement_ttl(pkt_route(pkt, next_hop_mac))
        exp_pkt_2 = (
            Ether(type=ETH_TYPE_CPU_LOOPBACK_EGRESS, src=ZERO_MAC, dst=ZERO_MAC)
            / routed_pkt
        )

        # The expected INT report packet
        exp_int_report_pkt = self.build_int_local_report(
            SWITCH_MAC,
            INT_COLLECTOR_MAC,
            SWITCH_IPV4,
            INT_COLLECTOR_IPV4,
            self.sdn_to_sdk_port[self.port1],
            self.sdn_to_sdk_port[self.port2],
            SWITCH_ID,
            routed_pkt,
            is_device_spine,
            send_report_to_spine,
        ).exp_pkt

        exp_int_report_pkt_loopback = (
            Ether(type=ETH_TYPE_CPU_LOOPBACK_EGRESS, src=ZERO_MAC, dst=ZERO_MAC)
            / exp_int_report_pkt
        )
        exp_int_report_pkt_masked = Mask(exp_int_report_pkt_loopback)
        exp_int_report_pkt_masked.set_do_not_care_scapy(Ether, "src")
        exp_int_report_pkt_masked.set_do_not_care_scapy(Ether, "dst")
        # IPv4 identification
        # The reason we also ignore IP checksum is because the `id` field is
        # random.
        exp_int_report_pkt_masked.set_do_not_care_scapy(IP, "id")
        exp_int_report_pkt_masked.set_do_not_care_scapy(IP, "chksum")
        exp_int_report_pkt_masked.set_do_not_care_scapy(UDP, "chksum")
        exp_int_report_pkt_masked.set_do_not_care_scapy(
            INT_L45_REPORT_FIXED, "ingress_tstamp"
        )
        exp_int_report_pkt_masked.set_do_not_care_scapy(INT_L45_REPORT_FIXED, "seq_no")
        exp_int_report_pkt_masked.set_do_not_care_scapy(
            INT_L45_LOCAL_REPORT, "queue_id"
        )
        exp_int_report_pkt_masked.set_do_not_care_scapy(
            INT_L45_LOCAL_REPORT, "queue_occupancy"
        )
        exp_int_report_pkt_masked.set_do_not_care_scapy(
            INT_L45_LOCAL_REPORT, "egress_tstamp"
        )

        # 1. step: packet-out straight to out port
        self.send_packet_out(
            self.build_packet_out(
                pkt, self.port1, cpu_loopback_mode=CPU_LOOPBACK_MODE_INGRESS
            )
        )
        self.verify_packet(exp_pkt_1, self.port1)

        # 2. step: send packet for normal ingress/egress processing
        self.send_packet(self.port1, exp_pkt_1)
        self.verify_packet(exp_pkt_2, self.port2)
        self.verify_packet(exp_int_report_pkt_masked, self.port3)

        # 3. step: packet-in
        self.send_packet(self.port2, exp_pkt_2)
        self.verify_packet_in(routed_pkt, self.port2)
        self.send_packet(self.port3, exp_int_report_pkt_loopback)
        self.verify_packet_in(exp_int_report_pkt, self.port3)
        self.verify_no_other_packets()

    def runTest(self):
        print("")
        for is_device_spine in [False, True]:
            for pkt_type in BASE_PKT_TYPES:
                print(
                    "Testing pkt={}, is_device_spine={}...".format(
                        pkt_type, is_device_spine
                    )
                )
                pkt = getattr(testutils, "simple_%s_packet" % pkt_type)(
                    eth_src=HOST1_MAC,
                    eth_dst=SWITCH_MAC,
                    ip_src=HOST1_IPV4,
                    ip_dst=self.get_single_use_ip(),  # To prevent the flow filter from dropping the report.
                    pktlen=MIN_PKT_LEN,
                )
                self.doRunTest(pkt, HOST2_MAC, is_device_spine)


@skipIf(is_v1model(), "Bmv2 is not subject to compiler field optimizations")
class FabricOptimizedFieldDetectorTest(FabricTest):
    """Finds action parameters or header fields that were optimized out by the
    compiler"""

    # Returns a byte string encoded value fitting into bitwidth.
    def generateBytestring(self, bitwidth, value=1):
        return stringify(value, (bitwidth + 7) // 8)

    # Since the test uses the same match key for tables with multiple actions,
    # each table entry has to be removed before testing the next.
    @autocleanup
    def insert_table_entry(
        self, table_name, match_keys, action_name, action_params, priority
    ):
        req, _ = self.send_request_add_entry_to_action(
            table_name, match_keys, action_name, action_params, priority
        )
        # Make a deep copy of the requests, because autocleanup will modify the
        # originals.
        write_entry = p4runtime_pb2.TableEntry()
        write_entry.CopyFrom(req.updates[0].entity.table_entry)
        resp = self.read_table_entry(table_name, match_keys, priority)
        if resp is None:
            self.fail(
                "Failed to read an entry that was just written! "
                'Table was "{}", action was "{}"'.format(table_name, action_name)
            )
        read_entry = p4runtime_pb2.TableEntry()
        read_entry.CopyFrom(resp)
        return write_entry, read_entry

    @autocleanup
    def insert_action_profile_member(
        self, action_profile_name, member_id, action_name, action_params
    ):
        req, _ = self.send_request_add_member(
            action_profile_name, member_id, action_name, action_params
        )
        # Make a deep copy of the requests, because autocleanup will modify the
        # originals.
        write_entry = p4runtime_pb2.ActionProfileMember()
        write_entry.CopyFrom(req.updates[0].entity.action_profile_member)
        read_entry = p4runtime_pb2.ActionProfileMember()
        read_entry.CopyFrom(
            self.read_action_profile_member(action_profile_name, member_id)
        )
        return write_entry, read_entry

    def handleTable(self, table):
        table_name = self.get_obj_name_from_id(table.preamble.id)
        priority = 0
        for action_ref in table.action_refs:
            # Build match
            match_keys = []
            for match in table.match_fields:
                if match.match_type == p4info_pb2.MatchField.MatchType.EXACT:
                    match_value = self.generateBytestring(match.bitwidth)
                    match_keys.append(self.Exact(match.name, match_value))
                elif match.match_type == p4info_pb2.MatchField.MatchType.LPM:
                    match_value = self.generateBytestring(match.bitwidth)
                    match_len = match.bitwidth
                    match_keys.append(self.Lpm(match.name, match_value, match_len))
                elif match.match_type == p4info_pb2.MatchField.MatchType.TERNARY:
                    match_value = self.generateBytestring(match.bitwidth)
                    # Use 0xfff...ff as mask
                    match_mask = self.generateBytestring(
                        match.bitwidth, (1 << match.bitwidth) - 1
                    )
                    match_keys.append(self.Ternary(match.name, match_value, match_mask))
                    priority = 1
                elif match.match_type == p4info_pb2.MatchField.MatchType.RANGE:
                    match_low = self.generateBytestring(match.bitwidth)
                    match_high = match_low
                    match_keys.append(self.Range(match.name, match_low, match_high))
                    priority = 1
                else:
                    print(
                        'Skipping table "%s" because it has a unsupported match field "%s" of type %s'
                        % (table_name, match.name, match.match_type)
                    )
                    return
            # Build action
            action_name = self.get_obj_name_from_id(action_ref.id)
            action = self.get_obj("actions", action_name)
            action_params = []
            if action_ref.scope == p4info_pb2.ActionRef.Scope.DEFAULT_ONLY:
                # Modify as default action
                match_keys = []
                priority = 0
            if table.const_default_action_id > 0 and len(match_keys) == 0:
                # Don't try to modify a const default action
                print(
                    'Skipping action "%s" of table "%s" because the default action is const'
                    % (action_name, table_name)
                )
                continue
            if table.is_const_table and len(match_keys) != 0:
                # Don't try to modify a table with const entries. The default
                # action might not be const, so we allow that.
                print(
                    'Skipping action "%s" of table "%s" because it has const'
                    " entries and the action is not a default action"
                    % (action_name, table_name)
                )
                continue
            for param in action.params:
                param_value = self.generateBytestring(param.bitwidth)
                action_params.append((param.name, param_value))

            write_entry = None
            read_entry = None
            if table.implementation_id > 0:
                action_profile_name = self.get_obj_name_from_id(table.implementation_id)
                action_profile = self.get_obj("action_profiles", action_profile_name)
                member_id = 1
                write_entry, read_entry = self.insert_action_profile_member(
                    action_profile_name, member_id, action_name, action_params
                )
                # TODO: Test table entries to members?
            else:
                write_entry, read_entry = self.insert_table_entry(
                    table_name, match_keys, action_name, action_params, priority
                )
            # Check for differences between expected and actual state.
            if write_entry != read_entry:
                write_entry_s = str.split(str(write_entry), "\n")
                read_entry_s = str.split(str(read_entry), "\n")
                diff = ""
                for line in difflib.unified_diff(
                    write_entry_s,
                    read_entry_s,
                    fromfile="Wrote",
                    tofile="Read back",
                    n=5,
                    lineterm="",
                ):
                    diff = diff + line + "\n"
                print(
                    'Found parameter that has been optimized out in action "%s" of table "%s":'
                    % (action_name, table_name)
                )
                print(diff)
                self.fail("Read does not match previous write!")

    @autocleanup
    def doRunTest(self):
        for table in getattr(self.p4info, "tables"):
            self.handleTable(table)

    def runTest(self):
        if self.generate_tv:
            return
        print("")
        self.doRunTest()


@group("int-dod")
@skipIf(is_v1model(), "Deflect on drop not supported in v1model.")
class FabricIntDeflectDropReportTest(IntTest):
    @autocleanup
    def doRunTest(
        self, pkt_type, tagged1=False, is_device_spine=False, send_report_to_spine=False
    ):
        print(
            f"Testing, pkt_type={pkt_type}, tagged1={tagged1}, "
            + f"is_device_spine={is_device_spine}, send_report_to_spine={send_report_to_spine}..."
        )
        pkt = getattr(testutils, f"simple_{pkt_type}_packet")(
            ip_dst=self.get_single_use_ip()
        )
        int_inner_pkt = pkt.copy()
        ig_port = self.port1
        eg_port = self.port2

        if tagged1:
            pkt = pkt_add_vlan(pkt, VLAN_ID_1)

        # The packet will still be routed, but dropped by traffic manager.
        # Note that the pipeline won't change IP TTL since the packet will not be
        # preceded by the egress next block.
        int_inner_pkt = pkt_route(int_inner_pkt, HOST2_MAC)

        # This is the WIP report packet which should be sent to the recirculation port according to
        # the deflect-on-drop configuration in the Stratum's chassis config. However, Tofino-model
        # always sends deflected packets to port 0, independently of the chassis config.
        # Here we check if the WIP packet is correct, and we re-inject it in the switch through the
        # recirculation port so the rest of pipeline can populate the rest of the header fields.
        exp_wip_int_pkt_masked = self.build_int_drop_report(
            0,  # both source and destination mac will be zero since it is a WIP packet.
            0,
            SWITCH_IPV4,
            INT_COLLECTOR_IPV4,
            self.sdn_to_sdk_port[ig_port],
            self.sdn_to_sdk_port[eg_port],
            INT_DROP_REASON_TRAFFIC_MANAGER,
            SWITCH_ID,
            int_inner_pkt,
            is_device_spine,
            send_report_to_spine,
            0,  # hw_id,
            truncate=False,  # packet will not be truncated
            wip_pkt=True,
        )

        exp_int_report_pkt_masked = self.build_int_drop_report(
            SWITCH_MAC,
            INT_COLLECTOR_MAC,
            SWITCH_IPV4,
            INT_COLLECTOR_IPV4,
            self.sdn_to_sdk_port[ig_port],
            self.sdn_to_sdk_port[eg_port],
            INT_DROP_REASON_TRAFFIC_MANAGER,
            SWITCH_ID,
            int_inner_pkt,
            is_device_spine,
            send_report_to_spine,
            0,  # hw_id,
            truncate=False,  # packet will not be truncated
        )

        self.set_up_int_flows(is_device_spine, pkt, send_report_to_spine)
        self.runIPv4UnicastTest(
            pkt=pkt,
            next_hop_mac=HOST2_MAC,
            tagged1=tagged1,
            tagged2=False,
            is_next_hop_spine=False,
            prefix_len=32,
            with_another_pkt_later=True,
            ig_port=ig_port,
            eg_port=eg_port,
            verify_pkt=False,
        )
        self.verify_packet(exp_wip_int_pkt_masked, self.port1)

        pkt_out = self.build_packet_out(
            exp_wip_int_pkt_masked.exp_pkt, RECIRCULATE_PORTS[0]
        )
        self.send_packet_out(pkt_out)
        self.verify_packet(exp_int_report_pkt_masked, self.port3)
        self.verify_no_other_packets()

    @autocleanup
    def send_dummy_packets(self):
        pkt = testutils.simple_tcp_packet()
        self.setup_port(self.port1, VLAN_ID_1, PORT_TYPE_EDGE)
        self.set_up_watchlist_flow(pkt[IP].src, pkt[IP].dst, None, None)
        self.add_forwarding_acl_set_output_port(self.port2, ipv4_dst=pkt[IP].dst)
        for _ in range(0, 9):
            # Add delay between each packet to make sure packets will be processed by
            # the Tofino Model correctly.
            time.sleep(0.05)
            self.send_packet(self.port1, pkt)
        self.verify_no_other_packets()

    def runTest(self):
        print("\n")
        for pkt_type in BASE_PKT_TYPES | GTP_PKT_TYPES | VXLAN_PKT_TYPES:
            # tagged2 will always be False since we are sending packet to the recirculate port.
            for tagged1 in [False, True]:
                for is_device_spine in [False, True]:
                    if is_device_spine and tagged1:
                        continue
                    for send_report_to_spine in [False, True]:
                        # When using Tofino Model with dod test mode, every 10th packet with
                        # deflect-on-drop flag set will be deflected.
                        # First we need to send 9 packets with deflect-on-drop flag set.
                        self.send_dummy_packets()
                        # The 10th packet will be deflected
                        self.doRunTest(
                            pkt_type, tagged1, is_device_spine, send_report_to_spine
                        )
