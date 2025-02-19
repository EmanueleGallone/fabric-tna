# SPDX-FileCopyrightText: Copyright 2020-present Open Networking Foundation.
# SPDX-License-Identifier: Apache-2.0

# This file contains line rate tests checking that our QoS targets are
# satisfied. For more information, see this doc:
# https://docs.google.com/document/d/1jq6NH-fffe8ImMo4EC_yMwH1djlrhWaQu2lpLFJKljA

import logging

import gnmi_utils
import qos_utils
import yaml
from base_test import *
from fabric_test import *
from ptf.testutils import group
from stratum_qos_config import vendor_config
from trex_stl_lib.api import STLFlowLatencyStats, STLPktBuilder, STLStream, STLTXCont
from trex_test import TRexTest
from trex_utils import *

# General test parameter.
LINK_RATE_BPS = 1 * G
EXPECTED_FLOW_RATE_WITH_STATS_BPS = 1 * G
TRAFFIC_DURATION_SECONDS = 10

# Maximum queue rates as per ChassisConfig.
CONTROL_QUEUE_MAX_RATE_BPS = 60 * M
REALTIME_1_QUEUE_MAX_RATE_BPS = 45 * M
REALTIME_2_QUEUE_MAX_RATE_BPS = 30 * M
REALTIME_3_QUEUE_MAX_RATE_BPS = 25 * M
SYSTEM_QUEUE_MAX_RATE_BPS = 10 * M

# WRR weights for Elastic queues as per ChassisConfig.
ELASTIC_1_WRR_WEIGHT = 330
ELASTIC_2_WRR_WEIGHT = 660
BEST_EFFORT_WRR_WEIGHT = 33

# Latency expectations for various traffic types in microseconds.
EXPECTED_MAXIMUM_LATENCY_CONTROL_TRAFFIC_US = 1000
EXPECTED_AVERAGE_LATENCY_CONTROL_TRAFFIC_US = 500
EXPECTED_99_9_PERCENTILE_LATENCY_CONTROL_TRAFFIC_US = 100
EXPECTED_MAXIMUM_LATENCY_REALTIME_TRAFFIC_US = 1500
EXPECTED_AVERAGE_LATENCY_REALTIME_TRAFFIC_US = 500
EXPECTED_99_9_PERCENTILE_LATENCY_REALTIME_TRAFFIC_US = 100

# Port setup.
BACKGROUND_SENDER_PORT = [0]
PRIORITY_SENDER_PORT = [2]
ALL_SENDER_PORTS = [0, 2]
RECEIVER_PORT = [1]
ALL_PORTS = [0, 1, 2, 3]


class QosTest(TRexTest, SlicingTest, StatsTest):
    def __init__(self):
        super().__init__()
        self.control_pg_id = 7
        self.system_pg_id = 2

    def push_chassis_config(self, yaml_file="qos-config-1g.yaml") -> None:
        this_dir = os.path.dirname(os.path.realpath(__file__))
        with open(f"{this_dir}/chassis_config.pb.txt", mode="rb") as file:
            chassis_config = file.read()
        # Auto-generate and append vendor_config
        with open(f"{this_dir}/{yaml_file}", "r") as file:
            chassis_config += bytes(
                "\n" + vendor_config(yaml.safe_load(file)), encoding="utf8"
            )
        # Write to disk for debugging
        with open(f"{this_dir}/chassis_config.pb.txt.tmp", mode="wb") as file:
            file.write(chassis_config)
        gnmi_utils.push_chassis_config(chassis_config)

    def _setup_basic_forwarding(self, out_port) -> None:
        in_ports = [self.port1, self.port2, self.port3, self.port4]
        for port in set(in_ports + [out_port]):
            self.setup_port(port, DEFAULT_VLAN, PORT_TYPE_EDGE)
        for in_port in in_ports:
            self.add_forwarding_acl_set_output_port(out_port, ig_port=in_port)

    def setup_basic_forwarding_to_1g(self) -> None:
        # Forwards all traffic to 1G shaped port per chassis config
        self._setup_basic_forwarding(out_port=self.port2)

    def setup_basic_forwarding_to_40g(self) -> None:
        # Forwards all traffic to 40G port per chassis config
        self._setup_basic_forwarding(out_port=self.port1)

    def setup_queue_classification(self) -> None:
        self.add_slice_tc_classifier_entry(
            slice_id=1, tc=0, l4_dport=qos_utils.L4_DPORT_CONTROL_TRAFFIC
        )
        self.add_queue_entry(1, 0, qos_utils.QUEUE_ID_CONTROL)
        self.add_slice_tc_classifier_entry(
            slice_id=2, tc=0, l4_dport=qos_utils.L4_DPORT_SYSTEM_TRAFFIC
        )
        self.add_queue_entry(2, 0, qos_utils.QUEUE_ID_SYSTEM)
        self.add_slice_tc_classifier_entry(
            slice_id=10, tc=0, l4_dport=qos_utils.L4_DPORT_REALTIME_TRAFFIC_1
        )
        self.add_slice_tc_classifier_entry(
            slice_id=11, tc=0, l4_dport=qos_utils.L4_DPORT_REALTIME_TRAFFIC_2
        )
        self.add_slice_tc_classifier_entry(
            slice_id=12, tc=0, l4_dport=qos_utils.L4_DPORT_REALTIME_TRAFFIC_3
        )
        self.add_queue_entry(10, 0, qos_utils.QUEUE_ID_REALTIME_1)
        self.add_queue_entry(11, 0, qos_utils.QUEUE_ID_REALTIME_2)
        self.add_queue_entry(12, 0, qos_utils.QUEUE_ID_REALTIME_3)
        self.add_slice_tc_classifier_entry(
            slice_id=13, tc=0, l4_dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_1
        )
        self.add_slice_tc_classifier_entry(
            slice_id=14, tc=0, l4_dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_2
        )
        self.add_queue_entry(13, 0, qos_utils.QUEUE_ID_ELASTIC_1)
        self.add_queue_entry(14, 0, qos_utils.QUEUE_ID_ELASTIC_2)

    def get_flow_stats_from_switch(
        self, stats_flow_id, ig_port, eg_port, **ftuple
    ) -> FlowStats:
        """
        Returns FlowStats populated using switch-maintained counters.
        Requires setting up counters beforehand with StatsTest.set_up_stats_flows().
        :param stats_flow_id: a unique identifier for this flow, could be the same as pg_id
        :param ig_port: the expected switch ingress port
        :param eg_port: the expected switch egress port
        :param ftuple: ACL-like five tuple keyworded parameters (ipv4_src, ipv4_dst, ip_proto, l4_sport, l4_dport)
        :return: FlowStats
        """
        ig_bytes, ig_packets = self.get_stats_counter(
            gress=STATS_INGRESS, stats_flow_id=stats_flow_id, port=ig_port, **ftuple
        )
        eg_bytes, eg_packets = self.get_stats_counter(
            gress=STATS_EGRESS, stats_flow_id=stats_flow_id, port=eg_port, **ftuple
        )
        # Switch egress bytes count will include bridged metadata, we need to subtract
        # that to obtain the actual bytes transmitted by the switch.
        eg_bytes = eg_bytes - eg_packets * BMD_BYTES
        # What is transmitted (tx) by Trex is received (rx) by the switch, and vice versa.
        return FlowStats(
            pg_id=stats_flow_id,
            tx_packets=ig_packets,
            rx_packets=eg_packets,
            tx_bytes=ig_bytes,
            rx_bytes=eg_bytes,
        )

    # Create a background traffic stream.
    def create_background_stream(self) -> STLStream:
        pkt = qos_utils.get_best_effort_traffic_packet()
        return STLStream(packet=STLPktBuilder(pkt=pkt), mode=STLTXCont(percentage=100))

    # Create a highest priority control stream.
    def create_control_stream(
        self, pg_id, l1_bps=CONTROL_QUEUE_MAX_RATE_BPS
    ) -> STLStream:
        pkt = qos_utils.get_control_traffic_packet(128)
        return STLStream(
            packet=STLPktBuilder(pkt=pkt),
            mode=STLTXCont(bps_L1=l1_bps),
            isg=50000,  # wait 50 ms till start to let queues fill up
            flow_stats=STLFlowLatencyStats(pg_id=pg_id),
        )

    # Create a highest priority control stream.
    def create_realtime_stream(
        self,
        pg_id,
        l1_bps=REALTIME_1_QUEUE_MAX_RATE_BPS,
        dport=qos_utils.L4_DPORT_REALTIME_TRAFFIC_1,
    ) -> STLStream:
        pkt = qos_utils.get_realtime_traffic_packet(128, dport=dport)
        return STLStream(
            packet=STLPktBuilder(pkt=pkt),
            mode=STLTXCont(bps_L1=l1_bps),
            isg=50000,  # wait 50 ms till start to let queues fill up
            flow_stats=STLFlowLatencyStats(pg_id=pg_id),
        )

    # Create a lower priority elastic stream.
    def create_elastic_stream(
        self,
        pg_id=None,
        l1_bps=LINK_RATE_BPS,
        dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_1,
        l2_size=750,
    ) -> STLStream:
        pkt = qos_utils.get_elastic_traffic_packet(l2_size=l2_size, dport=dport)
        stats = None
        if pg_id is not None:
            stats = STLFlowLatencyStats(pg_id=pg_id)
        return STLStream(
            packet=STLPktBuilder(pkt=pkt),
            mode=STLTXCont(bps_L1=l1_bps),
            flow_stats=stats,
        )

    # Create a lower priority best-effort stream.
    def create_best_effort_stream(
        self, pg_id=None, dport=None, l2_size=None, l1_bps=None,
    ) -> STLStream:
        pkt = qos_utils.get_best_effort_traffic_packet(l2_size=l2_size, dport=dport)
        stats = None
        if pg_id is not None:
            stats = STLFlowLatencyStats(pg_id=pg_id)
        return STLStream(
            packet=STLPktBuilder(pkt=pkt),
            mode=STLTXCont(bps_L1=l1_bps),
            flow_stats=stats,
        )

    # Create a second highest priority system stream.
    def create_system_stream(self, pg_id) -> STLStream:
        pkt = qos_utils.get_system_traffic_packet()
        return STLStream(
            packet=STLPktBuilder(pkt=pkt),
            mode=STLTXCont(bps_L1=SYSTEM_QUEUE_MAX_RATE_BPS),
            isg=50000,  # wait 50 ms till start to let queues fill up
            flow_stats=STLFlowLatencyStats(pg_id=pg_id),
        )


# Not executed by default, requires running Trex in SW mode:
#   TREX_PARAMS="--trex-sw-mode" ./ptf/run/hw/linerate fabric TEST=qos_tests.FlowCountersSanityTest
@group("trex-sw-mode")
class FlowCountersSanityTest(QosTest):
    """
    This test ensures that switch-maintained P4 counters can be used to produce
    the same flow stats obtained when using Trex. Trex per-flow stats require
    disabling NIC HW acceleration, which might limit the ability to analyze
    traffic at high rates. To avoid having to worry about the impact of Trex
    SW-based processing on QoS tests, we prefer to keep HW acceleration enabled
    for all other tests. This test serves as a guarantee that the switch P4
    counters can be reliably used in place of Trex per-flow stats.
    """

    @autocleanup
    def runTest(self) -> None:
        self.push_chassis_config()
        self.setup_basic_forwarding_to_1g()

        # Create multiple streams, each one sending at the link rate..
        stream_bps = LINK_RATE_BPS
        pg_id_1 = 1
        pg_id_2 = 2
        pg_id_3 = 3
        dport_1 = 100
        dport_2 = 200
        dport_3 = 300

        streams = [
            self.create_best_effort_stream(
                pg_id=pg_id_1, l1_bps=stream_bps, dport=dport_1, l2_size=1400
            ),
            self.create_best_effort_stream(
                pg_id=pg_id_2, l1_bps=stream_bps, dport=dport_2, l2_size=1400
            ),
            self.create_best_effort_stream(
                pg_id=pg_id_3, l1_bps=stream_bps, dport=dport_3, l2_size=1400
            ),
        ]

        switch_ig_port = self.port3  # Trex port 2
        switch_eg_port = self.port2  # Trex port 1

        self.set_up_stats_flows(
            stats_flow_id=pg_id_1,
            ig_port=switch_ig_port,
            eg_port=switch_eg_port,
            l4_dport=dport_1,
        )
        self.set_up_stats_flows(
            stats_flow_id=pg_id_2,
            ig_port=switch_ig_port,
            eg_port=switch_eg_port,
            l4_dport=dport_2,
        )
        self.set_up_stats_flows(
            stats_flow_id=pg_id_3,
            ig_port=switch_ig_port,
            eg_port=switch_eg_port,
            l4_dport=dport_3,
        )

        self.trex_client.add_streams(streams, ports=PRIORITY_SENDER_PORT)
        self.trex_client.start(
            PRIORITY_SENDER_PORT, mult="1", duration=TRAFFIC_DURATION_SECONDS
        )
        self.trex_client.wait_on_traffic(ports=PRIORITY_SENDER_PORT, rx_delay_ms=100)

        # Get and print TREX stats
        trex_stats = self.trex_client.get_stats()
        trex_flow_stats_1 = get_flow_stats(pg_id_1, trex_stats)
        print(get_readable_flow_stats(trex_flow_stats_1))
        trex_flow_stats_2 = get_flow_stats(pg_id_2, trex_stats)
        print(get_readable_flow_stats(trex_flow_stats_2))
        trex_flow_stats_3 = get_flow_stats(pg_id_3, trex_stats)
        print(get_readable_flow_stats(trex_flow_stats_3))

        for port in ALL_PORTS:
            readable_stats = get_readable_port_stats(trex_stats[port])
            print("Statistics for port {}: {}".format(port, readable_stats))

        # Get stats from switch
        switch_flow_stats_1 = self.get_flow_stats_from_switch(
            stats_flow_id=pg_id_1,
            ig_port=switch_ig_port,
            eg_port=switch_eg_port,
            l4_dport=dport_1,
        )
        switch_flow_stats_2 = self.get_flow_stats_from_switch(
            stats_flow_id=pg_id_2,
            ig_port=switch_ig_port,
            eg_port=switch_eg_port,
            l4_dport=dport_2,
        )
        switch_flow_stats_3 = self.get_flow_stats_from_switch(
            stats_flow_id=pg_id_3,
            ig_port=switch_ig_port,
            eg_port=switch_eg_port,
            l4_dport=dport_3,
        )

        # Compare Trex stats with switch stats
        self.assertEqual(trex_flow_stats_1.tx_packets, switch_flow_stats_1.tx_packets)
        self.assertEqual(trex_flow_stats_2.tx_packets, switch_flow_stats_2.tx_packets)
        self.assertEqual(trex_flow_stats_3.tx_packets, switch_flow_stats_3.tx_packets)
        self.assertEqual(trex_flow_stats_1.tx_bytes, switch_flow_stats_1.tx_bytes)
        self.assertEqual(trex_flow_stats_2.tx_bytes, switch_flow_stats_2.tx_bytes)
        self.assertEqual(trex_flow_stats_3.tx_bytes, switch_flow_stats_3.tx_bytes)

        self.assertEqual(trex_flow_stats_1.rx_packets, switch_flow_stats_1.rx_packets)
        self.assertEqual(trex_flow_stats_2.rx_packets, switch_flow_stats_2.rx_packets)
        self.assertEqual(trex_flow_stats_3.rx_packets, switch_flow_stats_3.rx_packets)
        self.assertEqual(trex_flow_stats_1.rx_bytes, switch_flow_stats_1.rx_bytes)
        self.assertEqual(trex_flow_stats_2.rx_bytes, switch_flow_stats_2.rx_bytes)
        self.assertEqual(trex_flow_stats_3.rx_bytes, switch_flow_stats_3.rx_bytes)


@group("trex-hw-mode")
class MinFlowrateWithSoftwareLatencyMeasurement(QosTest):
    # Create a highest priority control stream.
    def create_control_stream(self, pg_id) -> STLStream:
        pkt = qos_utils.get_control_traffic_packet(64)
        return STLStream(
            packet=STLPktBuilder(pkt=pkt),
            mode=STLTXCont(bps_L1=EXPECTED_FLOW_RATE_WITH_STATS_BPS),
            flow_stats=STLFlowLatencyStats(pg_id=pg_id),
        )

    @autocleanup
    def runTest(self):
        self.push_chassis_config()
        self.setup_basic_forwarding_to_1g()
        # Create the control stream
        control_stream = self.create_control_stream(self.control_pg_id)
        self.trex_client.add_streams(control_stream, ports=BACKGROUND_SENDER_PORT)
        # Start sending traffic
        logging.info("Starting traffic, duration: %d sec", TRAFFIC_DURATION_SECONDS)
        self.trex_client.start(
            BACKGROUND_SENDER_PORT, mult="1", duration=TRAFFIC_DURATION_SECONDS
        )
        logging.info("Waiting until all traffic is sent")
        self.trex_client.wait_on_traffic(ports=BACKGROUND_SENDER_PORT, rx_delay_ms=100)
        # Get latency stats
        stats = self.trex_client.get_stats()
        lat_stats = get_latency_stats(self.control_pg_id, stats)
        flow_stats = get_flow_stats(self.control_pg_id, stats)
        print(get_readable_latency_stats(lat_stats))
        tx_bps_L1 = stats[BACKGROUND_SENDER_PORT[0]].get("tx_bps_L1", 0)
        rx_bps_L1 = stats[RECEIVER_PORT[0]].get("rx_bps_L1", 0)
        # Get statistics for TX and RX ports
        for port in ALL_PORTS:
            readable_stats = get_readable_port_stats(stats[port])
            print("Statistics for port {}: {}".format(port, readable_stats))
        # Check that expected traffic rate can be achieved.
        self.assertGreater(
            flow_stats.rx_packets, 0, "No control traffic has been received"
        )
        self.assertGreaterEqual(
            tx_bps_L1,
            EXPECTED_FLOW_RATE_WITH_STATS_BPS * 0.95,
            "The achieved Tx rate {} is lower than the expected Tx rate of {}".format(
                to_readable(tx_bps_L1), to_readable(EXPECTED_FLOW_RATE_WITH_STATS_BPS)
            ),
        )
        self.assertGreaterEqual(
            rx_bps_L1,
            EXPECTED_FLOW_RATE_WITH_STATS_BPS * 0.95,
            "The measured RX rate {} is lower than the expected TX rate {}".format(
                to_readable(rx_bps_L1), to_readable(EXPECTED_FLOW_RATE_WITH_STATS_BPS)
            ),
        )
        self.assertLessEqual(
            rx_bps_L1,
            EXPECTED_FLOW_RATE_WITH_STATS_BPS * 1.05,
            "The measured RX rate {} is higher than the expected TX rate {}".format(
                to_readable(rx_bps_L1), to_readable(EXPECTED_FLOW_RATE_WITH_STATS_BPS)
            ),
        )


@group("trex-hw-mode")
class StrictPriorityControlTrafficIsPrioritized(QosTest):
    @autocleanup
    def runTest(self) -> None:
        self.push_chassis_config()
        self.setup_basic_forwarding_to_1g()
        self.setup_queue_classification()
        # Create a background traffic stream
        background_stream = self.create_background_stream()
        self.trex_client.add_streams(background_stream, ports=BACKGROUND_SENDER_PORT)
        # Create the control stream
        control_stream = self.create_control_stream(self.control_pg_id)
        self.trex_client.add_streams(control_stream, ports=PRIORITY_SENDER_PORT)
        # Create the system stream
        system_stream = self.create_system_stream(self.system_pg_id)
        self.trex_client.add_streams(system_stream, ports=PRIORITY_SENDER_PORT)
        # Start sending traffic
        logging.info("Starting traffic, duration: %d sec", TRAFFIC_DURATION_SECONDS)
        self.trex_client.start(
            ALL_SENDER_PORTS, mult="1", duration=TRAFFIC_DURATION_SECONDS
        )
        logging.info("Waiting until all traffic is sent")
        self.trex_client.wait_on_traffic(ports=ALL_SENDER_PORTS, rx_delay_ms=100)
        # Get latency stats
        stats = self.trex_client.get_stats()
        lat_stats = get_latency_stats(self.control_pg_id, stats)
        flow_stats = get_flow_stats(self.control_pg_id, stats)
        print(get_readable_latency_stats(lat_stats))
        # Get statistics for TX and RX ports
        for port in ALL_PORTS:
            readable_stats = get_readable_port_stats(stats[port])
            print("Statistics for port {}: {}".format(port, readable_stats))
        # Check that SLAs are met.
        self.assertGreater(
            flow_stats.rx_packets, 0, "No control traffic has been received"
        )
        self.assertEqual(
            lat_stats.dropped,
            0,
            f"Control traffic has been dropped: {lat_stats.dropped}",
        )
        self.assertEqual(
            lat_stats.seq_too_high,
            0,
            f"Control traffic has been dropped or reordered: {lat_stats.seq_too_high}",
        )
        self.assertEqual(
            lat_stats.seq_too_low,
            0,
            f"Control traffic has been dropped or reordered: {lat_stats.seq_too_low}",
        )
        self.assertLessEqual(
            lat_stats.percentile_99_9,
            EXPECTED_99_9_PERCENTILE_LATENCY_CONTROL_TRAFFIC_US,
            f"99.9th percentile latency in control traffic is too high: {lat_stats.percentile_99_9}",
        )


@group("trex-hw-mode")
class ControlTrafficIsNotPrioritizedWithoutRules(QosTest):
    @autocleanup
    def runTest(self) -> None:
        self.push_chassis_config()
        self.setup_basic_forwarding_to_1g()
        # Create a background traffic stream
        background_stream = self.create_background_stream()
        self.trex_client.add_streams(background_stream, ports=BACKGROUND_SENDER_PORT)
        # Create the control stream
        control_stream = self.create_control_stream(self.control_pg_id)
        self.trex_client.add_streams(control_stream, ports=PRIORITY_SENDER_PORT)
        # Create the system stream
        system_stream = self.create_system_stream(self.system_pg_id)
        self.trex_client.add_streams(system_stream, ports=PRIORITY_SENDER_PORT)
        # Start sending traffic
        logging.info("Starting traffic, duration: %d sec", TRAFFIC_DURATION_SECONDS)
        self.trex_client.start(
            ALL_SENDER_PORTS, mult="1", duration=TRAFFIC_DURATION_SECONDS
        )
        logging.info("Waiting until all traffic is sent")
        self.trex_client.wait_on_traffic(ports=ALL_SENDER_PORTS, rx_delay_ms=100)
        # Get latency stats
        stats = self.trex_client.get_stats()
        lat_stats = get_latency_stats(self.control_pg_id, stats)
        flow_stats = get_flow_stats(self.control_pg_id, stats)
        print(get_readable_latency_stats(lat_stats))
        # Get statistics for TX and RX ports
        for port in ALL_PORTS:
            readable_stats = get_readable_port_stats(stats[port])
            print("Statistics for port {}: {}".format(port, readable_stats))
        # Check that SLAs are NOT met.
        self.assertGreater(
            flow_stats.rx_packets, 0, "No control traffic has been received"
        )
        self.assertGreater(
            lat_stats.dropped,
            0,
            f"Control traffic has not been dropped: {lat_stats.dropped}",
        )
        self.assertGreater(
            lat_stats.seq_too_high + lat_stats.seq_too_low,
            0,
            f"Control traffic has not been dropped or reordered: sequence to high {lat_stats.seq_too_high}, sequence to low {lat_stats.seq_too_low}",
        )
        self.assertGreaterEqual(
            lat_stats.total_max,
            EXPECTED_MAXIMUM_LATENCY_CONTROL_TRAFFIC_US,
            f"Maximum latency in control traffic is not over the expected limit: {lat_stats.total_max}",
        )
        self.assertGreaterEqual(
            lat_stats.percentile_99_9,
            EXPECTED_99_9_PERCENTILE_LATENCY_CONTROL_TRAFFIC_US,
            f"99.9th percentile latency in control traffic not over the expected limit: {lat_stats.percentile_99_9}",
        )


@group("trex-hw-mode")
class ControlTrafficIsShaped(QosTest):
    @autocleanup
    def runTest(self) -> None:
        self.push_chassis_config()
        self.setup_basic_forwarding_to_1g()
        self.setup_queue_classification()
        # Create the control stream with above maximum allocated rate
        control_stream = self.create_control_stream(
            self.control_pg_id, CONTROL_QUEUE_MAX_RATE_BPS * 1.1
        )
        self.trex_client.add_streams(control_stream, ports=PRIORITY_SENDER_PORT)
        # Start sending traffic
        logging.info("Starting traffic, duration: %d sec", TRAFFIC_DURATION_SECONDS)
        self.trex_client.start(
            PRIORITY_SENDER_PORT, mult="1", duration=TRAFFIC_DURATION_SECONDS
        )
        logging.info("Waiting until all traffic is sent")
        self.trex_client.wait_on_traffic(ports=PRIORITY_SENDER_PORT, rx_delay_ms=100)
        # Get latency stats
        stats = self.trex_client.get_stats()
        lat_stats = get_latency_stats(self.control_pg_id, stats)
        flow_stats = get_flow_stats(self.control_pg_id, stats)
        rx_port_stats = get_port_stats(RECEIVER_PORT[0], stats)
        # Get statistics for TX and RX ports
        for port in ALL_PORTS:
            readable_stats = get_readable_port_stats(stats[port])
            print("Statistics for port {}: {}".format(port, readable_stats))
        # Check that rate limits are enforced.
        self.assertGreater(
            flow_stats.rx_packets, 0, "No control traffic has been received"
        )
        self.assertGreater(
            lat_stats.dropped,
            0,
            f"Control traffic has not been dropped: {lat_stats.dropped}",
        )
        self.assertLessEqual(
            rx_port_stats.rx_bps_L1,
            CONTROL_QUEUE_MAX_RATE_BPS * 1.01,  # allow small marging of error
            f"Control traffic has not been rate limtied: {rx_port_stats.rx_bps_L1}",
        )
        self.assertGreaterEqual(
            lat_stats.total_max,
            EXPECTED_MAXIMUM_LATENCY_CONTROL_TRAFFIC_US,
            f"Maximum latency in control traffic is not over the expected limit: {lat_stats.total_max}",
        )
        self.assertGreaterEqual(
            lat_stats.percentile_99_9,
            EXPECTED_99_9_PERCENTILE_LATENCY_CONTROL_TRAFFIC_US,
            f"99.9th percentile latency in control traffic not over the expected limit: {lat_stats.percentile_99_9}",
        )


@group("trex-hw-mode")
class RealtimeTrafficIsRrScheduled(QosTest):
    """
    In this test we check that well behaved realtime traffic is not negatively
    impacted by other realtime flows that are not. For this we start 3 streams
    and assign them to separate queues. Stream 1 and 2 will send more than their
    alloted rate, while stream 3 is within limits. We expect that stream 3 will
    experience the lowest latency and no packet drops, while the other streams should.
    """

    @autocleanup
    def runTest(self) -> None:
        self.realtime_pg_id_1 = 1
        self.realtime_pg_id_2 = 2
        self.realtime_pg_id_3 = 3
        self.push_chassis_config()
        self.setup_basic_forwarding_to_1g()
        self.setup_queue_classification()
        # Create multiple realtime streams. Stream 1 and 2 send more than the
        # alloted rate, while stream 3 is well behaved.
        rt_streams = [
            self.create_realtime_stream(
                self.realtime_pg_id_1,
                l1_bps=REALTIME_1_QUEUE_MAX_RATE_BPS * 1.1,
                dport=qos_utils.L4_DPORT_REALTIME_TRAFFIC_1,
            ),
            self.create_realtime_stream(
                self.realtime_pg_id_2,
                l1_bps=REALTIME_2_QUEUE_MAX_RATE_BPS * 1.1,
                dport=qos_utils.L4_DPORT_REALTIME_TRAFFIC_2,
            ),
            self.create_realtime_stream(
                self.realtime_pg_id_3,
                l1_bps=REALTIME_3_QUEUE_MAX_RATE_BPS * 1.0,
                dport=qos_utils.L4_DPORT_REALTIME_TRAFFIC_3,
            ),
        ]
        self.trex_client.add_streams(rt_streams, ports=PRIORITY_SENDER_PORT)
        # Start sending traffic
        logging.info("Starting traffic, duration: %d sec", TRAFFIC_DURATION_SECONDS)
        self.trex_client.start(
            PRIORITY_SENDER_PORT, mult="1", duration=TRAFFIC_DURATION_SECONDS
        )
        logging.info("Waiting until all traffic is sent")
        self.trex_client.wait_on_traffic(ports=PRIORITY_SENDER_PORT, rx_delay_ms=100)
        # Get latency stats
        stats = self.trex_client.get_stats()
        # Check RT stream 1
        lat_stats_1 = get_latency_stats(self.realtime_pg_id_1, stats)
        flow_stats_1 = get_flow_stats(self.realtime_pg_id_1, stats)
        print(get_readable_latency_stats(lat_stats_1))
        self.assertGreater(
            flow_stats_1.rx_packets, 0, "No realtime traffic has been received"
        )
        self.assertGreater(
            lat_stats_1.dropped,
            0,
            f"Non-compliant realtime traffic has not been dropped: {lat_stats_1.dropped}",
        )
        self.assertGreaterEqual(
            lat_stats_1.total_max,
            EXPECTED_MAXIMUM_LATENCY_REALTIME_TRAFFIC_US,
            f"Maximum latency in realtime traffic is not over the expected limit: {lat_stats_1.total_max}",
        )
        self.assertGreaterEqual(
            lat_stats_1.percentile_99_9,
            EXPECTED_99_9_PERCENTILE_LATENCY_REALTIME_TRAFFIC_US,
            f"99.9th percentile latency in realtime traffic is is not over the expected limit: {lat_stats_1.percentile_99_9}",
        )
        # Check RT stream 2
        lat_stats_2 = get_latency_stats(self.realtime_pg_id_2, stats)
        flow_stats_2 = get_flow_stats(self.realtime_pg_id_2, stats)
        print(get_readable_latency_stats(lat_stats_2))
        self.assertGreater(
            flow_stats_2.rx_packets, 0, "No realtime traffic has been received"
        )
        self.assertGreater(
            lat_stats_2.dropped,
            0,
            f"Non-compliant realtime traffic has not been dropped: {lat_stats_2.dropped}",
        )
        self.assertGreaterEqual(
            lat_stats_2.total_max,
            EXPECTED_MAXIMUM_LATENCY_REALTIME_TRAFFIC_US,
            f"Maximum latency in control traffic is not over the expected limit: {lat_stats_2.total_max}",
        )
        self.assertGreaterEqual(
            lat_stats_2.percentile_99_9,
            EXPECTED_99_9_PERCENTILE_LATENCY_REALTIME_TRAFFIC_US,
            f"99.9th percentile latency in realtime traffic is is not over the expected limit: {lat_stats_2.percentile_99_9}",
        )
        # Check RT stream 3
        lat_stats_3 = get_latency_stats(self.realtime_pg_id_3, stats)
        flow_stats_3 = get_flow_stats(self.realtime_pg_id_3, stats)
        print(get_readable_latency_stats(lat_stats_3))
        self.assertGreater(
            flow_stats_3.rx_packets, 0, "No realtime traffic has been received"
        )
        self.assertEqual(
            lat_stats_3.dropped,
            0,
            f"Realtime traffic has been dropped: {lat_stats_3.dropped}",
        )
        self.assertLessEqual(
            lat_stats_3.percentile_99_9,
            EXPECTED_99_9_PERCENTILE_LATENCY_REALTIME_TRAFFIC_US,
            f"99th percentile latency in well behaved realtime traffic is too high: {lat_stats_3.percentile_99_9}",
        )
        # Get statistics for TX and RX ports
        for port in ALL_PORTS:
            readable_stats = get_readable_port_stats(stats[port])
            print("Statistics for port {}: {}".format(port, readable_stats))


@group("trex-hw-mode")
class ElasticTrafficIsWrrScheduled(QosTest):
    """
    In this test we check that traffic using elastic queues (including
    best-effort) is scheduled in a WRR fashion. For this, we start three
    streams each one sending more than the allotted rate, thus congesting the
    output link. We expect that the amount of bytes received for each stream is
    proportional to the WRR weights.
    """

    def runTest(self) -> None:
        print("\nTesting 1G bottleneck...")
        self.doRunTest(link_bps=1 * G)

        # FIXME: flow stats report egress link utilization greater than 100% and incorrect RX shares.
        #   Could be an issue with the switch counters, or something's wrong with the scheduler
        #   trying to send more than 40Gbps.
        # print("\nTesting 40G bottleneck...")
        # self.doRunTest(link_bps=40 * G)

    @autocleanup
    def doRunTest(self, link_bps) -> None:
        elastic_flow_id_1 = 1
        elastic_flow_id_2 = 2
        best_effort_flow_id_3 = 3

        self.push_chassis_config()
        self.setup_queue_classification()

        # NOTE: this might be common to other test cases wanting to test different
        # bottlenecks. Consider moving to base class QosTest.
        if link_bps == 1 * G:
            switch_out_port = self.port2
            self.setup_basic_forwarding_to_1g()
        elif link_bps == 40 * G:
            switch_out_port = self.port1
            self.setup_basic_forwarding_to_40g()
        else:
            raise Exception(f"Invalid link_bps: {link_bps}")

        # Use one port per stream to make sure we have enough bandwidth to congest all
        # queues event with a 40Gbps bottleneck.
        switch_in_ports = [self.port1, self.port3, self.port4]
        trex_tx_ports = [0, 2, 3]

        # To guarantee that the perceived WRR scheduling does not depend on the input
        # rate, all streams should send at the same rate. Also, we make sure to create
        # congestion on all queues so the scheduler doesn't experience idle cycles (and we
        # don't need to account for that in the assertions). To this end, we configure
        # each stream to send at a rate higher than the expected scheduling rate of the
        # queue with the highest weight.
        weight_total = (
            ELASTIC_1_WRR_WEIGHT + ELASTIC_2_WRR_WEIGHT + BEST_EFFORT_WRR_WEIGHT
        )
        weight_1 = ELASTIC_1_WRR_WEIGHT / weight_total
        weight_2 = ELASTIC_2_WRR_WEIGHT / weight_total
        weight_3 = BEST_EFFORT_WRR_WEIGHT / weight_total

        weight_max = max(weight_1, weight_2, weight_3)
        min_tx_stream_bps = link_bps * weight_max
        tx_stream_bps = min_tx_stream_bps * 1.1

        assert (
            tx_stream_bps <= 40 * G
        ), "Not enough input bandwidth to create congestion on all queues"

        stream_1 = self.create_elastic_stream(
            l1_bps=tx_stream_bps,
            dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_1,
            l2_size=1400,
        )
        stream_2 = self.create_elastic_stream(
            l1_bps=tx_stream_bps,
            dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_2,
            l2_size=1400,
        )
        stream_3 = self.create_best_effort_stream(
            l1_bps=tx_stream_bps,
            dport=qos_utils.L4_DPORT_BEST_EFFORT_TRAFFIC_1,
            l2_size=1400,
        )

        self.trex_client.add_streams(stream_1, ports=trex_tx_ports[0])
        self.trex_client.add_streams(stream_2, ports=trex_tx_ports[1])
        self.trex_client.add_streams(stream_3, ports=trex_tx_ports[2])

        # We rely on switch counters to evaluate the scheduling accuracy.
        ig_port_1 = switch_in_ports[0]
        ig_port_2 = switch_in_ports[1]
        ig_port_3 = switch_in_ports[2]
        eg_port = switch_out_port

        self.set_up_stats_flows(
            stats_flow_id=elastic_flow_id_1,
            ig_port=ig_port_1,
            eg_port=eg_port,
            l4_dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_1,
        )
        self.set_up_stats_flows(
            stats_flow_id=elastic_flow_id_2,
            ig_port=ig_port_2,
            eg_port=eg_port,
            l4_dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_2,
        )
        self.set_up_stats_flows(
            stats_flow_id=best_effort_flow_id_3,
            ig_port=ig_port_3,
            eg_port=eg_port,
            l4_dport=qos_utils.L4_DPORT_BEST_EFFORT_TRAFFIC_1,
        )

        logging.info("Starting traffic, duration: %d sec", TRAFFIC_DURATION_SECONDS)
        self.trex_client.start(
            trex_tx_ports, mult="1", duration=TRAFFIC_DURATION_SECONDS
        )
        logging.info("Waiting until all traffic is sent")
        self.trex_client.wait_on_traffic(ports=trex_tx_ports, rx_delay_ms=100)

        trex_stats = self.trex_client.get_stats()
        for port in ALL_PORTS:
            readable_stats = get_readable_port_stats(trex_stats[port])
            print("Statistics for port {}: {}".format(port, readable_stats))

        flow_stats_1 = self.get_flow_stats_from_switch(
            stats_flow_id=elastic_flow_id_1,
            ig_port=ig_port_1,
            eg_port=eg_port,
            l4_dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_1,
        )
        flow_stats_2 = self.get_flow_stats_from_switch(
            stats_flow_id=elastic_flow_id_2,
            ig_port=ig_port_2,
            eg_port=eg_port,
            l4_dport=qos_utils.L4_DPORT_ELASTIC_TRAFFIC_2,
        )
        flow_stats_3 = self.get_flow_stats_from_switch(
            stats_flow_id=best_effort_flow_id_3,
            ig_port=ig_port_3,
            eg_port=eg_port,
            l4_dport=qos_utils.L4_DPORT_BEST_EFFORT_TRAFFIC_1,
        )
        print(get_readable_flow_stats(flow_stats_1))
        print(get_readable_flow_stats(flow_stats_2))
        print(get_readable_flow_stats(flow_stats_3))

        flow_rate_shares = get_flow_rate_shares(
            TRAFFIC_DURATION_SECONDS, flow_stats_1, flow_stats_2, flow_stats_3,
        )
        print(get_readable_flow_rate_shares(flow_rate_shares))

        self.assertGreater(
            flow_rate_shares.tx_bps[elastic_flow_id_1],
            min_tx_stream_bps,
            "TX bps for elastic source 1 was not enough to congest the queue",
        )
        self.assertGreater(
            flow_rate_shares.tx_bps[elastic_flow_id_2],
            min_tx_stream_bps,
            "TX bps for elastic source 2 was not enough to congest the queue",
        )
        self.assertGreater(
            flow_rate_shares.tx_bps[best_effort_flow_id_3],
            min_tx_stream_bps,
            "TX bps for best-effort source 3 was not enough to congest the queue",
        )
        self.assertAlmostEqual(
            flow_rate_shares.tx_shares[elastic_flow_id_1],
            flow_rate_shares.tx_shares[elastic_flow_id_2],
            delta=0.001,
            msg="All streams should send at the same rate",
        )
        self.assertAlmostEqual(
            flow_rate_shares.tx_shares[elastic_flow_id_1],
            flow_rate_shares.tx_shares[best_effort_flow_id_3],
            delta=0.001,
            msg="All streams should send at the same rate",
        )
        self.assertAlmostEqual(
            flow_rate_shares.rx_bps_total / link_bps,
            1,
            delta=0.02,
            msg=f"Egress link utilization should be almost 100%",
        )
        self.assertAlmostEqual(
            flow_rate_shares.rx_shares[elastic_flow_id_1],
            weight_1,
            delta=0.008,
            msg="Elastic source 1 was not scheduled as expected",
        )
        self.assertAlmostEqual(
            flow_rate_shares.rx_shares[elastic_flow_id_2],
            weight_2,
            delta=0.008,
            msg="Elastic source 2 was not scheduled as expected",
        )
        self.assertAlmostEqual(
            flow_rate_shares.rx_shares[best_effort_flow_id_3],
            weight_3,
            delta=0.008,
            msg="Best-effort source 3 was not scheduled as expected",
        )
