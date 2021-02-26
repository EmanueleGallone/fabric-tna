// Copyright 2020-present Open Networking Foundation
// SPDX-License-Identifier: LicenseRef-ONF-Member-Only-1.0
package org.stratumproject.fabric.tna.behaviour;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.ImmutableSet;
import com.google.common.collect.Lists;
import com.google.common.collect.Sets;
import org.easymock.Capture;
import org.easymock.CaptureType;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.onlab.junit.TestUtils;
import org.onlab.packet.EthType;
import org.onlab.packet.Ethernet;
import org.onlab.packet.IPv4;
import org.onlab.packet.IpAddress;
import org.onlab.packet.IpPrefix;
import org.onlab.packet.MacAddress;
import org.onlab.packet.TpPort;
import org.onlab.util.HexString;
import org.onlab.util.ImmutableByteSequence;
import org.onosproject.TestApplicationId;
import org.onosproject.core.ApplicationId;
import org.onosproject.core.CoreService;
import org.onosproject.net.DefaultHost;
import org.onosproject.net.DeviceId;
import org.onosproject.net.Host;
import org.onosproject.net.HostLocation;
import org.onosproject.net.PortNumber;
import org.onosproject.net.behaviour.inbandtelemetry.IntDeviceConfig;
import org.onosproject.net.behaviour.inbandtelemetry.IntMetadataType;
import org.onosproject.net.behaviour.inbandtelemetry.IntObjective;
import org.onosproject.net.behaviour.inbandtelemetry.IntProgrammable;
import org.onosproject.net.config.NetworkConfigService;
import org.onosproject.net.driver.DriverData;
import org.onosproject.net.driver.DriverHandler;
import org.onosproject.net.flow.DefaultFlowEntry;
import org.onosproject.net.flow.DefaultFlowRule;
import org.onosproject.net.flow.DefaultTrafficSelector;
import org.onosproject.net.flow.DefaultTrafficTreatment;
import org.onosproject.net.flow.FlowEntry;
import org.onosproject.net.flow.FlowRule;
import org.onosproject.net.flow.FlowRuleService;
import org.onosproject.net.flow.TrafficSelector;
import org.onosproject.net.flow.TrafficTreatment;
import org.onosproject.net.flow.criteria.Criteria;
import org.onosproject.net.flow.criteria.PiCriterion;
import org.onosproject.net.group.DefaultGroupDescription;
import org.onosproject.net.group.DefaultGroupKey;
import org.onosproject.net.group.GroupBucket;
import org.onosproject.net.group.GroupBuckets;
import org.onosproject.net.group.GroupDescription;
import org.onosproject.net.group.GroupService;
import org.onosproject.net.host.HostService;
import org.onosproject.net.pi.runtime.PiAction;
import org.onosproject.net.pi.runtime.PiActionParam;
import org.onosproject.segmentrouting.config.SegmentRoutingDeviceConfig;
import org.stratumproject.fabric.tna.PipeconfLoader;

import java.io.IOException;
import java.io.InputStream;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

import static org.easymock.EasyMock.anyObject;
import static org.easymock.EasyMock.anyString;
import static org.easymock.EasyMock.capture;
import static org.easymock.EasyMock.createMock;
import static org.easymock.EasyMock.eq;
import static org.easymock.EasyMock.expect;
import static org.easymock.EasyMock.expectLastCall;
import static org.easymock.EasyMock.newCapture;
import static org.easymock.EasyMock.replay;
import static org.easymock.EasyMock.reset;
import static org.easymock.EasyMock.verify;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.onosproject.net.group.DefaultGroupBucket.createCloneGroupBucket;
import static org.stratumproject.fabric.tna.behaviour.FabricUtils.KRYO;

/**
 * Tests for fabric INT programmable behaviour.
 */
public class FabricIntProgrammableTest {
    private static final int NODE_SID_IPV4 = 101;
    private static final IpAddress ROUTER_IP = IpAddress.valueOf("10.0.1.254");
    private static final String SR_CONFIG_KEY = "segmentrouting";
    private static final ApplicationId APP_ID =
            TestApplicationId.create(PipeconfLoader.APP_NAME);
    private static final DeviceId LEAF_DEVICE_ID = DeviceId.deviceId("device:1");
    private static final DeviceId SPINE_DEVICE_ID = DeviceId.deviceId("device:2");
    private static final IpPrefix IP_SRC = IpPrefix.valueOf("10.0.0.1/24");
    private static final IpPrefix IP_DST = IpPrefix.valueOf("10.0.0.2/24");
    private static final TpPort L4_SRC = TpPort.tpPort(30000);
    private static final TpPort L4_DST = TpPort.tpPort(32767);
    private static final int DEFAULT_PRIORITY = 10000;
    private static final IpAddress COLLECTOR_IP = IpAddress.valueOf("10.128.0.1");
    private static final TpPort COLLECTOR_PORT = TpPort.tpPort(32766);
    private static final short BMD_TYPE_EGRESS_MIRROR = 2;
    private static final short BMD_TYPE_INGRESS_MIRROR = 3;
    private static final short MIRROR_TYPE_INT_REPORT = 1;
    private static final short INT_REPORT_TYPE_LOCAL = 1;
    private static final short INT_REPORT_TYPE_DROP = 2;
    private static final HostLocation COLLECTOR_LOCATION = new HostLocation(LEAF_DEVICE_ID, PortNumber.P0, 0);
    private static final Host COLLECTOR_HOST =
            new DefaultHost(null, null, null, null, COLLECTOR_LOCATION, Sets.newHashSet());
    private static final ImmutableByteSequence DEFAULT_TIMESTAMP_MASK =
            ImmutableByteSequence.copyFrom(
                    HexString.fromHexString("ffffc0000000", ""));
    private static final ImmutableByteSequence DEFAULT_QMASK = ImmutableByteSequence.copyFrom(
            HexString.fromHexString("00000000ffffff00", ""));
    private static final Map<Integer, Integer> QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS =
            ImmutableMap.<Integer, Integer>builder()
                    .put(300, 0x44)
                    .put(301, 0xc4)
                    .put(302, 0x144)
                    .put(303, 0x1c4).build();
    private static final int DEFAULT_VLAN = 4094;
    private static final MacAddress SWITCH_MAC = MacAddress.valueOf("00:00:00:00:01:80");
    private static final byte FWD_TYPE_MPLS = 1;
    private static final byte FWD_TYPE_IPV4_ROUTING = 2;
    private static final short ETH_TYPE_EXACT_MASK = (short) 0xFFFF;

    private FabricIntProgrammable intProgrammable;
    private FabricCapabilities capabilities;
    private FlowRuleService flowRuleService;
    private GroupService groupService;
    private NetworkConfigService netcfgService;
    private CoreService coreService;
    private HostService hostService;
    private DriverData driverData;

    @Before
    public void setup() throws IOException {
        capabilities = createMock(FabricCapabilities.class);
        expect(capabilities.hasHashedTable()).andReturn(true).anyTimes();
        expect(capabilities.supportDoubleVlanTerm()).andReturn(false).anyTimes();
        expect(capabilities.hwPipeCount()).andReturn(4).anyTimes();
        replay(capabilities);

        // Services mock
        flowRuleService = createMock(FlowRuleService.class);
        groupService = createMock(GroupService.class);
        netcfgService = createMock(NetworkConfigService.class);
        coreService = createMock(CoreService.class);
        hostService = createMock(HostService.class);
        expect(coreService.getAppId(anyString())).andReturn(APP_ID).anyTimes();

        expect(netcfgService.getConfig(LEAF_DEVICE_ID, SegmentRoutingDeviceConfig.class))
                .andReturn(getSrConfig(LEAF_DEVICE_ID, "/sr.json")).anyTimes();
        expect(netcfgService.getConfig(SPINE_DEVICE_ID, SegmentRoutingDeviceConfig.class))
                .andReturn(getSrConfig(SPINE_DEVICE_ID, "/sr-spine.json")).anyTimes();
        expect(hostService.getHostsByIp(COLLECTOR_IP)).andReturn(ImmutableSet.of(COLLECTOR_HOST)).anyTimes();
        replay(coreService, netcfgService, hostService);

        DriverHandler driverHandler = createMock(DriverHandler.class);
        expect(driverHandler.get(FlowRuleService.class)).andReturn(flowRuleService).anyTimes();
        expect(driverHandler.get(GroupService.class)).andReturn(groupService).anyTimes();
        expect(driverHandler.get(NetworkConfigService.class)).andReturn(netcfgService).anyTimes();
        expect(driverHandler.get(CoreService.class)).andReturn(coreService).anyTimes();
        expect(driverHandler.get(HostService.class)).andReturn(hostService).anyTimes();
        replay(driverHandler);

        driverData = createMock(DriverData.class);
        expect(driverData.deviceId()).andReturn(LEAF_DEVICE_ID).anyTimes();
        replay(driverData);

        intProgrammable = new FabricIntProgrammable(capabilities);
        TestUtils.setField(intProgrammable, "handler", driverHandler);
        TestUtils.setField(intProgrammable, "data", driverData);

        testDefaultRecirculateRules();
    }

    @After
    public void teardown() {
        reset(flowRuleService, groupService, netcfgService, coreService);
    }

    /**
     * Test "setSourcePort" function of IntProgrammable.
     * Note that we don't implement this functionality in this pipeconf
     * since we only support postcard mode.
     * We should expect the function returns true without installing
     * any table or group entries.
     */
    @Test
    public void testSetSourcePort() {
        assertTrue(intProgrammable.setSourcePort(PortNumber.ANY));
    }

    /**
     * Test "setSinkPort" function of IntProgrammable.
     * Note that we don't implement this functionality in this pipeconf
     * since we only support postcard mode.
     * We should expect the function returns true without installing
     * any table or group entries.
     */
    @Test
    public void testSetSinkPort() {
        assertTrue(intProgrammable.setSinkPort(PortNumber.ANY));
    }

    /**
     * Test "addIntObjective" function of IntProgrammable.
     */
    @Test
    public void testAddIntObjective() {
        reset(flowRuleService);
        List<FlowRule> expectedFlows = ImmutableList.of(
                buildExpectedCollectorFlow(IPv4.PROTOCOL_TCP),
                buildExpectedCollectorFlow(IPv4.PROTOCOL_UDP),
                buildExpectedCollectorFlow(IPv4.PROTOCOL_ICMP)
        );
        List<Capture<FlowRule>> captures = Lists.newArrayList();
        for (int i = 0; i < expectedFlows.size(); i++) {
            Capture<FlowRule> flowRuleCapture = newCapture();
            flowRuleService.applyFlowRules(capture(flowRuleCapture));
            captures.add(flowRuleCapture);
        }
        replay(flowRuleService);
        assertTrue(intProgrammable.addIntObjective(buildIntObjective(IPv4.PROTOCOL_TCP)));
        assertTrue(intProgrammable.addIntObjective(buildIntObjective(IPv4.PROTOCOL_UDP)));
        assertTrue(intProgrammable.addIntObjective(buildIntObjective(IPv4.PROTOCOL_ICMP)));
        for (int i = 0; i < expectedFlows.size(); i++) {
            FlowRule expectFlow = expectedFlows.get(i);
            FlowRule actualFlow = captures.get(i).getValue();
            assertTrue(expectFlow.exactMatch(actualFlow));
        }
        verify(flowRuleService);

    }

    /**
     * Test "addIntObjective" function of IntProgrammable with an
     * invalid match criteria.
     */
    @Test
    public void testAddUnsupportedIntObjective() {
        reset(flowRuleService);
        IntObjective intObjective = buildInvalidIntObjective();
        replay(flowRuleService);
        assertFalse(intProgrammable.addIntObjective(intObjective));
        verify(flowRuleService);
    }

    /**
     * Test "removeIntObjective" function of IntProgrammable.
     */
    @Test
    public void testRemoveIntObjective() {
        // TCP
        IntObjective intObjective = buildIntObjective(IPv4.PROTOCOL_TCP);
        FlowRule expectedFlow = buildExpectedCollectorFlow(IPv4.PROTOCOL_TCP);
        reset(flowRuleService);
        flowRuleService.removeFlowRules(eq(expectedFlow));
        expectLastCall().andVoid().once();
        replay(flowRuleService);
        assertTrue(intProgrammable.removeIntObjective(intObjective));
        verify(flowRuleService);

        // UDP
        intObjective = buildIntObjective(IPv4.PROTOCOL_UDP);
        expectedFlow = buildExpectedCollectorFlow(IPv4.PROTOCOL_UDP);
        reset(flowRuleService);
        flowRuleService.removeFlowRules(eq(expectedFlow));
        expectLastCall().andVoid().once();
        replay(flowRuleService);
        assertTrue(intProgrammable.removeIntObjective(intObjective));
        verify(flowRuleService);

        // Don't match L4 ports
        intObjective = buildIntObjective(IPv4.PROTOCOL_ICMP);
        expectedFlow = buildExpectedCollectorFlow(IPv4.PROTOCOL_ICMP);
        reset(flowRuleService);
        flowRuleService.removeFlowRules(eq(expectedFlow));
        expectLastCall().andVoid().once();
        replay(flowRuleService);
        assertTrue(intProgrammable.removeIntObjective(intObjective));
        verify(flowRuleService);
    }

    /**
     * Test "setupIntConfig" function of IntProgrammable.
     */
    @Test
    public void testSetupIntConfig() {
        reset(flowRuleService);
        final IntDeviceConfig intConfig = buildIntDeviceConfig();
        ImmutableList<FlowRule> expectRules = ImmutableList.of(
                buildReportTableRule(LEAF_DEVICE_ID, false, BMD_TYPE_EGRESS_MIRROR, INT_REPORT_TYPE_LOCAL),
                buildReportTableRule(LEAF_DEVICE_ID, false, BMD_TYPE_EGRESS_MIRROR, INT_REPORT_TYPE_DROP),
                buildReportTableRule(LEAF_DEVICE_ID, false, BMD_TYPE_INGRESS_MIRROR, INT_REPORT_TYPE_LOCAL),
                buildReportTableRule(LEAF_DEVICE_ID, false, BMD_TYPE_INGRESS_MIRROR, INT_REPORT_TYPE_DROP),
                buildFilterConfigFlow(LEAF_DEVICE_ID),
                buildIntMetadataLocalRule(LEAF_DEVICE_ID),
                buildIntMetadataDropRule(LEAF_DEVICE_ID),
                buildIngressDropReportTableRules(LEAF_DEVICE_ID).get(0),
                buildIngressDropReportTableRules(LEAF_DEVICE_ID).get(1)
        );

        List<Capture<FlowRule>> captures = Lists.newArrayList();
        for (int i = 0; i < expectRules.size(); i++) {
            Capture<FlowRule> flowRuleCapture = newCapture();
            flowRuleService.applyFlowRules(capture(flowRuleCapture));
            captures.add(flowRuleCapture);
        }

        // Forwarding classifier rules will also be updated again
        final List<FlowRule> expectedFwdClsIpRules = Lists.newArrayList();
        final Capture<FlowRule> capturedFwdClsIpRules = newCapture(CaptureType.ALL);
        final List<FlowRule> expectedFwdClsMplsRules = Lists.newArrayList();
        final Capture<FlowRule> capturedFwdClsMplsRules = newCapture(CaptureType.ALL);
        QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS.forEach((sessionId, port) -> {
            // Fwd classifier match IPv4
            PiCriterion criterion = PiCriterion.builder()
                    .matchExact(P4InfoConstants.HDR_IP_ETH_TYPE, Ethernet.TYPE_IPV4)
                    .build();
            TrafficSelector fwdClassSel = DefaultTrafficSelector.builder()
                    .matchInPort(PortNumber.portNumber(port))
                    .matchEthDstMasked(SWITCH_MAC, MacAddress.EXACT_MASK)
                    .matchPi(criterion)
                    .build();
            PiActionParam fwdTypeParam = new PiActionParam(P4InfoConstants.FWD_TYPE, FWD_TYPE_IPV4_ROUTING);
            PiAction setFwdTypeAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_INGRESS_FILTERING_SET_FORWARDING_TYPE)
                    .withParameter(fwdTypeParam)
                    .build();
            TrafficTreatment treatment = DefaultTrafficTreatment.builder()
                    .piTableAction(setFwdTypeAction)
                    .build();
            expectedFwdClsIpRules.add(DefaultFlowRule.builder()
                    .withSelector(fwdClassSel)
                    .withTreatment(treatment)
                    .forTable(P4InfoConstants.FABRIC_INGRESS_FILTERING_FWD_CLASSIFIER)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY)
                    .forDevice(LEAF_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());
            flowRuleService.applyFlowRules(capture(capturedFwdClsIpRules));

            // Fwd classifier match MPLS + IPv4
            criterion = PiCriterion.builder()
                    .matchTernary(P4InfoConstants.HDR_ETH_TYPE,
                            EthType.EtherType.MPLS_UNICAST.ethType().toShort(),
                            ETH_TYPE_EXACT_MASK)
                    .matchExact(P4InfoConstants.HDR_IP_ETH_TYPE, EthType.EtherType.IPV4.ethType().toShort())
                    .build();
            fwdClassSel = DefaultTrafficSelector.builder()
                    .matchInPort(PortNumber.portNumber(port))
                    .matchEthDstMasked(SWITCH_MAC, MacAddress.EXACT_MASK)
                    .matchPi(criterion)
                    .build();
            fwdTypeParam = new PiActionParam(P4InfoConstants.FWD_TYPE, FWD_TYPE_MPLS);
            setFwdTypeAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_INGRESS_FILTERING_SET_FORWARDING_TYPE)
                    .withParameter(fwdTypeParam)
                    .build();
            treatment = DefaultTrafficTreatment.builder()
                    .piTableAction(setFwdTypeAction)
                    .build();
            expectedFwdClsMplsRules.add(DefaultFlowRule.builder()
                    .withSelector(fwdClassSel)
                    .withTreatment(treatment)
                    .forTable(P4InfoConstants.FABRIC_INGRESS_FILTERING_FWD_CLASSIFIER)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY + 10)
                    .forDevice(LEAF_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());
            flowRuleService.applyFlowRules(capture(capturedFwdClsMplsRules));
        });

        replay(flowRuleService);
        assertTrue(intProgrammable.setupIntConfig(intConfig));

        // Verifying flow rules
        for (int i = 0; i < expectRules.size(); i++) {
            FlowRule expectRule = expectRules.get(i);
            FlowRule actualRule = captures.get(i).getValue();
            assertTrue(expectRule.exactMatch(actualRule));
        }
        for (int i = 0; i < QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS.size(); i++) {
            FlowRule expectedFwdClsIpRule = expectedFwdClsIpRules.get(i);
            FlowRule actualFwdClsIpRule = capturedFwdClsIpRules.getValues().get(i);
            FlowRule expectedFwdClsMplsRule = expectedFwdClsMplsRules.get(i);
            FlowRule actualFwdClsMplsRule = capturedFwdClsMplsRules.getValues().get(i);
            assertTrue(expectedFwdClsIpRule.exactMatch(actualFwdClsIpRule));
            assertTrue(expectedFwdClsMplsRule.exactMatch(actualFwdClsMplsRule));
        }
        verify(flowRuleService);
    }

    /**
     * Test "setupIntConfig" function of IntProgrammable for spine device.
     * We should expected to get a table entry for report table
     * with do_report_encap_mpls action.
     */
    @Test
    public void testSetupIntConfigOnSpine() {
        // Override the driver device id data.
        reset(driverData);
        expect(driverData.deviceId()).andReturn(SPINE_DEVICE_ID).anyTimes();
        replay(driverData);
        reset(flowRuleService);
        final IntDeviceConfig intConfig = buildIntDeviceConfig();
        ImmutableList<FlowRule> expectRules = ImmutableList.of(
                buildReportTableRule(SPINE_DEVICE_ID, true, BMD_TYPE_EGRESS_MIRROR, INT_REPORT_TYPE_LOCAL),
                buildReportTableRule(SPINE_DEVICE_ID, true, BMD_TYPE_EGRESS_MIRROR, INT_REPORT_TYPE_DROP),
                buildReportTableRule(SPINE_DEVICE_ID, true, BMD_TYPE_INGRESS_MIRROR, INT_REPORT_TYPE_LOCAL),
                buildReportTableRule(SPINE_DEVICE_ID, true, BMD_TYPE_INGRESS_MIRROR, INT_REPORT_TYPE_DROP),
                buildFilterConfigFlow(SPINE_DEVICE_ID),
                buildIntMetadataLocalRule(SPINE_DEVICE_ID),
                buildIntMetadataDropRule(SPINE_DEVICE_ID),
                buildIngressDropReportTableRules(SPINE_DEVICE_ID).get(0),
                buildIngressDropReportTableRules(SPINE_DEVICE_ID).get(1)
        );

        List<Capture<FlowRule>> captures = Lists.newArrayList();
        for (int i = 0; i < expectRules.size(); i++) {
            Capture<FlowRule> flowRuleCapture = newCapture();
            flowRuleService.applyFlowRules(capture(flowRuleCapture));
            captures.add(flowRuleCapture);
        }

        // Forwarding classifier rules will also be updated again
        final List<FlowRule> expectedFwdClsIpRules = Lists.newArrayList();
        final Capture<FlowRule> capturedFwdClsIpRules = newCapture(CaptureType.ALL);
        final List<FlowRule> expectedFwdClsMplsRules = Lists.newArrayList();
        final Capture<FlowRule> capturedFwdClsMplsRules = newCapture(CaptureType.ALL);
        QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS.forEach((sessionId, port) -> {
            // Fwd classifier match IPv4
            PiCriterion criterion = PiCriterion.builder()
                    .matchExact(P4InfoConstants.HDR_IP_ETH_TYPE, Ethernet.TYPE_IPV4)
                    .build();
            TrafficSelector fwdClassSel = DefaultTrafficSelector.builder()
                    .matchInPort(PortNumber.portNumber(port))
                    .matchEthDstMasked(SWITCH_MAC, MacAddress.EXACT_MASK)
                    .matchPi(criterion).build();
            PiActionParam fwdTypeParam = new PiActionParam(P4InfoConstants.FWD_TYPE, FWD_TYPE_IPV4_ROUTING);
            PiAction setFwdTypeAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_INGRESS_FILTERING_SET_FORWARDING_TYPE)
                    .withParameter(fwdTypeParam)
                    .build();
            TrafficTreatment treatment = DefaultTrafficTreatment.builder()
                    .piTableAction(setFwdTypeAction)
                    .build();
            expectedFwdClsIpRules.add(DefaultFlowRule.builder()
                    .withSelector(fwdClassSel)
                    .withTreatment(treatment)
                    .forTable(P4InfoConstants.FABRIC_INGRESS_FILTERING_FWD_CLASSIFIER)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY)
                    .forDevice(SPINE_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());
            flowRuleService.applyFlowRules(capture(capturedFwdClsIpRules));

            // Fwd classifier match MPLS + IPv4
            criterion = PiCriterion.builder()
                    .matchTernary(P4InfoConstants.HDR_ETH_TYPE,
                            EthType.EtherType.MPLS_UNICAST.ethType().toShort(),
                            ETH_TYPE_EXACT_MASK)
                    .matchExact(P4InfoConstants.HDR_IP_ETH_TYPE,
                            EthType.EtherType.IPV4.ethType().toShort())
                    .build();
            fwdClassSel = DefaultTrafficSelector.builder()
                    .matchInPort(PortNumber.portNumber(port))
                    .matchEthDstMasked(SWITCH_MAC, MacAddress.EXACT_MASK)
                    .matchPi(criterion).build();
            fwdTypeParam = new PiActionParam(P4InfoConstants.FWD_TYPE, FWD_TYPE_MPLS);
            setFwdTypeAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_INGRESS_FILTERING_SET_FORWARDING_TYPE)
                    .withParameter(fwdTypeParam)
                    .build();
            treatment = DefaultTrafficTreatment.builder()
                    .piTableAction(setFwdTypeAction)
                    .build();
            expectedFwdClsMplsRules.add(DefaultFlowRule.builder()
                    .withSelector(fwdClassSel)
                    .withTreatment(treatment)
                    .forTable(P4InfoConstants.FABRIC_INGRESS_FILTERING_FWD_CLASSIFIER)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY + 10)
                    .forDevice(SPINE_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());
            flowRuleService.applyFlowRules(capture(capturedFwdClsMplsRules));
        });
        replay(flowRuleService);
        assertTrue(intProgrammable.setupIntConfig(intConfig));

        // Verifying flow rules
        for (int i = 0; i < expectRules.size(); i++) {
            FlowRule expectRule = expectRules.get(i);
            FlowRule actualRule = captures.get(i).getValue();
            assertTrue(expectRule.exactMatch(actualRule));
        }
        for (int i = 0; i < QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS.size(); i++) {
            FlowRule expectedFwdClsIpRule = expectedFwdClsIpRules.get(i);
            FlowRule actualFwdClsIpRule = capturedFwdClsIpRules.getValues().get(i);
            FlowRule expectedFwdClsMplsRule = expectedFwdClsMplsRules.get(i);
            FlowRule actualFwdClsMplsRule = capturedFwdClsMplsRules.getValues().get(i);
            assertTrue(expectedFwdClsIpRule.exactMatch(actualFwdClsIpRule));
            assertTrue(expectedFwdClsMplsRule.exactMatch(actualFwdClsMplsRule));
        }
        verify(flowRuleService);
    }

    @Test
    public void testSupportsFunctionality() {
        assertFalse(intProgrammable.supportsFunctionality(IntProgrammable.IntFunctionality.SOURCE));
        assertFalse(intProgrammable.supportsFunctionality(IntProgrammable.IntFunctionality.TRANSIT));
        assertFalse(intProgrammable.supportsFunctionality(IntProgrammable.IntFunctionality.SINK));
        assertTrue(intProgrammable.supportsFunctionality(IntProgrammable.IntFunctionality.POSTCARD));
    }

    @Test
    public void testUtilityMethods() {
        assertEquals(0xffffffffL, intProgrammable.getSuitableQmaskForLatencyChange(0));
        assertEquals(0xffffffffL, intProgrammable.getSuitableQmaskForLatencyChange(1));
        assertEquals(0xfffffffeL, intProgrammable.getSuitableQmaskForLatencyChange(2));
        assertEquals(0xffffff00L, intProgrammable.getSuitableQmaskForLatencyChange(256));
        assertEquals(0xffffff00L, intProgrammable.getSuitableQmaskForLatencyChange(300));
        assertEquals(0xffff0000L, intProgrammable.getSuitableQmaskForLatencyChange(65536));
        assertEquals(0xffff0000L, intProgrammable.getSuitableQmaskForLatencyChange(100000));
        assertEquals(0xf0000000L, intProgrammable.getSuitableQmaskForLatencyChange(1 << 28));
        assertEquals(0xf0000000L, intProgrammable.getSuitableQmaskForLatencyChange((1 << 28) + 10));
        assertEquals(0xc0000000L, intProgrammable.getSuitableQmaskForLatencyChange(1 << 30));
        assertEquals(0xc0000000L, intProgrammable.getSuitableQmaskForLatencyChange(0x40000000));
        assertEquals(0xc0000000L, intProgrammable.getSuitableQmaskForLatencyChange(0x7fffffff));

        // Illegal argument.
        try {
            intProgrammable.getSuitableQmaskForLatencyChange(-1);
        } catch (IllegalArgumentException e) {
            assertEquals(e.getMessage(),
                    "Flow latency change value must equal or greater than zero.");
        }
    }

    @Test
    public void testCleanup() {
        Set<FlowEntry> intEntries = ImmutableSet.of(
                // Watchlist table entry
                buildFlowEntry(buildExpectedCollectorFlow(IPv4.PROTOCOL_TCP)),
                buildFlowEntry(buildExpectedCollectorFlow(IPv4.PROTOCOL_UDP)),
                buildFlowEntry(buildExpectedCollectorFlow(IPv4.PROTOCOL_ICMP)),
                // Report table entry
                buildFlowEntry(buildFilterConfigFlow(LEAF_DEVICE_ID)),
                buildFlowEntry(buildReportTableRule(LEAF_DEVICE_ID, false,
                        BMD_TYPE_EGRESS_MIRROR, INT_REPORT_TYPE_LOCAL)),
                buildFlowEntry(buildReportTableRule(LEAF_DEVICE_ID, false,
                        BMD_TYPE_EGRESS_MIRROR, INT_REPORT_TYPE_DROP)),
                buildFlowEntry(buildReportTableRule(LEAF_DEVICE_ID, false,
                        BMD_TYPE_INGRESS_MIRROR, INT_REPORT_TYPE_LOCAL)),
                buildFlowEntry(buildReportTableRule(LEAF_DEVICE_ID, false,
                        BMD_TYPE_INGRESS_MIRROR, INT_REPORT_TYPE_DROP)),
                // INT mirror table entry
                buildFlowEntry(buildIntMetadataLocalRule(LEAF_DEVICE_ID)),
                buildFlowEntry(buildIntMetadataDropRule(LEAF_DEVICE_ID))
        );
        Set<FlowEntry> randomEntries = buildRandomFlowEntries();
        Set<FlowEntry> entries = Sets.newHashSet(intEntries);
        entries.addAll(randomEntries);
        reset(flowRuleService);
        expect(flowRuleService.getFlowEntries(LEAF_DEVICE_ID))
                .andReturn(entries)
                .anyTimes();
        intEntries.forEach(e -> {
            flowRuleService.removeFlowRules(e);
            expectLastCall().once();
        });
        replay(flowRuleService);
        intProgrammable.cleanup();
        verify(flowRuleService);
    }

    /**
     * Test when setup behaviour failed.
     */
    @Test
    public void testSetupBehaviourFailed() {
        reset(coreService);
        expect(coreService.getAppId(anyString())).andReturn(null).anyTimes();
        replay(coreService, flowRuleService);
        assertFalse(intProgrammable.init());
        assertFalse(intProgrammable.setupIntConfig(null));
        assertFalse(intProgrammable.addIntObjective(null));
        assertFalse(intProgrammable.removeIntObjective(null));
        intProgrammable.cleanup();

        // Here we expected no flow entries installed
        verify(flowRuleService);
    }

    @Test
    public void testInvalidConfig() {
        reset(netcfgService);
        expect(netcfgService.getConfig(LEAF_DEVICE_ID, SegmentRoutingDeviceConfig.class))
                .andReturn(null).anyTimes();
        replay(netcfgService, flowRuleService);
        final IntDeviceConfig intConfig = buildIntDeviceConfig();
        final IntObjective intObjective = buildIntObjective(IPv4.PROTOCOL_TCP);
        assertFalse(intProgrammable.setupIntConfig(intConfig));
        assertFalse(intProgrammable.addIntObjective(intObjective));
        assertFalse(intProgrammable.removeIntObjective(intObjective));
        // We expected no other flow rules be installed or removed
        verify(flowRuleService);
    }

    /**
     * Test installing report rules on spine but collector host not found.
     */
    @Test
    public void testSetUpSpineButCollectorHostNotFound() {
        reset(driverData, hostService);
        expect(driverData.deviceId()).andReturn(SPINE_DEVICE_ID).anyTimes();
        expect(hostService.getHostsByIp(anyObject())).andReturn(Collections.emptySet()).anyTimes();
        replay(driverData, hostService, flowRuleService);
        final IntDeviceConfig intConfig = buildIntDeviceConfig();
        assertFalse(intProgrammable.setupIntConfig(intConfig));
        // We expect no flow rules be installed
        verify(flowRuleService);
    }

    /**
     * Test installing report rules on spine but cannot find
     * the location of the collector host.
     */
    @Test
    public void testSetUpSpineButNoCollectorHostLocation() {
        reset(driverData, hostService);
        expect(driverData.deviceId()).andReturn(SPINE_DEVICE_ID).anyTimes();
        final Host collectorHost = new DefaultHost(null, null, null, null, Sets.newHashSet(), Sets.newHashSet(), true);
        expect(hostService.getHostsByIp(COLLECTOR_IP)).andReturn(ImmutableSet.of(collectorHost)).anyTimes();
        replay(driverData, hostService, flowRuleService);
        final IntDeviceConfig intConfig = buildIntDeviceConfig();
        assertFalse(intProgrammable.setupIntConfig(intConfig));
        verify(flowRuleService);
    }

    /**
     * Test installing report rules on spine but cannot find
     * the segment routing config of the leaf.
     */
    @Test
    public void testSetUpSpineButNoLeafConfig() throws IOException {
        reset(driverData, netcfgService);
        expect(driverData.deviceId()).andReturn(SPINE_DEVICE_ID).anyTimes();
        expect(netcfgService.getConfig(LEAF_DEVICE_ID, SegmentRoutingDeviceConfig.class))
                .andReturn(null).anyTimes();
        expect(netcfgService.getConfig(SPINE_DEVICE_ID, SegmentRoutingDeviceConfig.class))
                .andReturn(getSrConfig(SPINE_DEVICE_ID, "/sr-spine.json")).anyTimes();
        replay(driverData, flowRuleService, netcfgService);
        final IntDeviceConfig intConfig = buildIntDeviceConfig();
        assertFalse(intProgrammable.setupIntConfig(intConfig));
        verify(flowRuleService);
    }

    /**
     * Test installing report rules on spine but the config
     * of leaf is invalid.
     */
    @Test
    public void testSetUpSpineButInvalidLeafConfig() throws IOException {
        reset(driverData, netcfgService);
        expect(driverData.deviceId()).andReturn(SPINE_DEVICE_ID).anyTimes();
        expect(netcfgService.getConfig(LEAF_DEVICE_ID, SegmentRoutingDeviceConfig.class))
                .andReturn(getSrConfig(SPINE_DEVICE_ID, "/sr-invalid.json")).anyTimes();
        expect(netcfgService.getConfig(SPINE_DEVICE_ID, SegmentRoutingDeviceConfig.class))
                .andReturn(getSrConfig(SPINE_DEVICE_ID, "/sr-spine.json")).anyTimes();
        replay(driverData, flowRuleService, netcfgService);
        final IntDeviceConfig intConfig = buildIntDeviceConfig();
        assertFalse(intProgrammable.setupIntConfig(intConfig));
        verify(flowRuleService);
    }

    private PiAction buildReportAction(boolean setMpls, short reportType) {
        final PiActionParam srcMacParam = new PiActionParam(
                P4InfoConstants.SRC_MAC, MacAddress.ZERO.toBytes());
        final PiActionParam nextHopMacParam = new PiActionParam(
                P4InfoConstants.MON_MAC, SWITCH_MAC.toBytes());
        final PiActionParam srcIpParam = new PiActionParam(
                P4InfoConstants.SRC_IP, ROUTER_IP.toOctets());
        final PiActionParam monIpParam = new PiActionParam(
                P4InfoConstants.MON_IP,
                COLLECTOR_IP.toOctets());
        final PiActionParam monPortParam = new PiActionParam(
                P4InfoConstants.MON_PORT,
                COLLECTOR_PORT.toInt());
        final PiAction.Builder reportAction = PiAction.builder()
                .withParameter(srcMacParam)
                .withParameter(nextHopMacParam)
                .withParameter(srcIpParam)
                .withParameter(monIpParam)
                .withParameter(monPortParam);
        if (setMpls) {
            reportAction.withParameter(new PiActionParam(
                    P4InfoConstants.MON_LABEL,
                    NODE_SID_IPV4
            ));
            if (reportType == INT_REPORT_TYPE_LOCAL) {
                reportAction.withId(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_DO_LOCAL_REPORT_ENCAP_MPLS);
            } else {
                reportAction.withId(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_DO_DROP_REPORT_ENCAP_MPLS);
            }
        } else {
            if (reportType == INT_REPORT_TYPE_LOCAL) {
                reportAction.withId(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_DO_LOCAL_REPORT_ENCAP);
            } else {
                reportAction.withId(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_DO_DROP_REPORT_ENCAP);
            }
        }
        return reportAction.build();
    }

    private FlowRule buildReportTableRule(DeviceId deviceId, boolean setMpls, short bmdType, short reportType) {
        PiAction reportAction = buildReportAction(setMpls, reportType);
        final TrafficTreatment treatment = DefaultTrafficTreatment.builder()
                .piTableAction(reportAction)
                .build();
        final TrafficSelector selector = DefaultTrafficSelector.builder()
                .matchPi(PiCriterion.builder()
                        .matchExact(P4InfoConstants.HDR_BMD_TYPE, bmdType)
                        .matchExact(P4InfoConstants.HDR_MIRROR_TYPE,
                                MIRROR_TYPE_INT_REPORT)
                        .matchExact(P4InfoConstants.HDR_INT_REPORT_TYPE, reportType)
                        .build())
                .build();
        return DefaultFlowRule.builder()
                .withSelector(selector)
                .withTreatment(treatment)
                .fromApp(APP_ID)
                .withPriority(DEFAULT_PRIORITY)
                .makePermanent()
                .forDevice(deviceId)
                .forTable(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_REPORT)
                .build();
    }

    private FlowRule buildFilterConfigFlow(DeviceId deviceId) {
        final PiActionParam hopLatencyMask = new PiActionParam(P4InfoConstants.HOP_LATENCY_MASK, DEFAULT_QMASK);
        final PiActionParam timestampMask = new PiActionParam(P4InfoConstants.TIMESTAMP_MASK, DEFAULT_TIMESTAMP_MASK);
        final PiAction quantizeAction =
                PiAction.builder()
                        .withId(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_SET_CONFIG)
                        .withParameter(hopLatencyMask)
                        .withParameter(timestampMask)
                        .build();
        final TrafficTreatment quantizeTreatment = DefaultTrafficTreatment.builder()
                .piTableAction(quantizeAction)
                .build();
        return DefaultFlowRule.builder()
                .forDevice(deviceId)
                .makePermanent()
                .withPriority(DEFAULT_PRIORITY)
                .withTreatment(quantizeTreatment)
                .fromApp(APP_ID)
                .forTable(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_CONFIG)
                .build();
    }

    private IntObjective buildIntObjective(byte protocol) {
        TrafficSelector.Builder sBuilder = DefaultTrafficSelector.builder()
                .matchIPSrc(IP_SRC)
                .matchIPDst(IP_DST);

        switch (protocol) {
            case IPv4.PROTOCOL_UDP:
                sBuilder.matchUdpSrc(L4_SRC).matchUdpDst(L4_DST);
                break;
            case IPv4.PROTOCOL_TCP:
                sBuilder.matchTcpSrc(L4_SRC).matchTcpDst(L4_DST);
                break;
            default:
                // do nothing
                break;
        }

        // The metadata type doesn't affect the result, however we still need to pass
        // a non-empty set to the objective since the builder won't allow an empty
        // set of INT metadata types.
        Set<IntMetadataType> metadataTypes = ImmutableSet.of(IntMetadataType.SWITCH_ID);
        return new IntObjective.Builder()
                .withSelector(sBuilder.build())
                .withMetadataTypes(metadataTypes)
                .build();
    }

    private IntObjective buildInvalidIntObjective() {
        TrafficSelector selector = DefaultTrafficSelector.builder()
                .matchEthType((short) 10)
                .build();

        // The metadata type doesn't affect the result, however we still need to pass
        // a non-empty set to the objective since the builder won't allow an empty
        // set of INT metadata types.
        Set<IntMetadataType> metadataTypes = ImmutableSet.of(IntMetadataType.SWITCH_ID);
        return new IntObjective.Builder()
                .withSelector(selector)
                .withMetadataTypes(metadataTypes)
                .build();
    }

    private FlowRule buildExpectedCollectorFlow(byte protocol) {
        // Flow rule that we expected.
        TrafficSelector.Builder expectedSelector = DefaultTrafficSelector.builder();
        expectedSelector.matchIPSrc(IP_SRC);
        expectedSelector.matchIPDst(IP_DST);
        if (protocol == IPv4.PROTOCOL_TCP || protocol == IPv4.PROTOCOL_UDP) {
            expectedSelector.matchPi(
                    PiCriterion.builder().matchRange(
                            P4InfoConstants.HDR_L4_SPORT,
                            L4_SRC.toInt(),
                            L4_SRC.toInt())
                            .build());
            expectedSelector.matchPi(
                    PiCriterion.builder().matchRange(
                            P4InfoConstants.HDR_L4_DPORT,
                            L4_DST.toInt(),
                            L4_DST.toInt())
                            .build());
        }
        PiAction expectedPiAction = PiAction.builder()
                .withId(P4InfoConstants.FABRIC_INGRESS_INT_INGRESS_MARK_TO_REPORT)
                .build();
        TrafficTreatment expectedTreatment = DefaultTrafficTreatment.builder()
                .piTableAction(expectedPiAction)
                .build();
        return DefaultFlowRule.builder()
                .forDevice(LEAF_DEVICE_ID)
                .withSelector(expectedSelector.build())
                .withTreatment(expectedTreatment)
                .fromApp(APP_ID)
                .withPriority(DEFAULT_PRIORITY)
                .forTable(P4InfoConstants.FABRIC_INGRESS_INT_INGRESS_WATCHLIST)
                .makePermanent()
                .build();
    }

    private IntDeviceConfig buildIntDeviceConfig() {
        return IntDeviceConfig.builder()
                .enabled(true)
                .withCollectorIp(COLLECTOR_IP)
                .withCollectorPort(COLLECTOR_PORT)
                .withSinkIp(IpAddress.valueOf("10.192.19.180"))
                .withSinkMac(MacAddress.NONE)
                .withCollectorNextHopMac(MacAddress.BROADCAST)
                .withMinFlowHopLatencyChangeNs(300)
                .build();
    }

    private FlowEntry buildFlowEntry(FlowRule flowRule) {
        return new DefaultFlowEntry(flowRule, FlowEntry.FlowEntryState.ADDED, 1, TimeUnit.SECONDS, 0, 0);
    }

    private SegmentRoutingDeviceConfig getSrConfig(DeviceId deviceId, String fileName) throws IOException {
        SegmentRoutingDeviceConfig srCfg = new SegmentRoutingDeviceConfig();
        InputStream jsonStream = getClass().getResourceAsStream(fileName);
        ObjectMapper mapper = new ObjectMapper();
        JsonNode jsonNode = mapper.readTree(jsonStream);
        srCfg.init(deviceId, SR_CONFIG_KEY, jsonNode, mapper, config -> {
        });
        return srCfg;
    }

    private Set<FlowEntry> buildRandomFlowEntries() {
        FlowRule rule1 = DefaultFlowRule.builder()
                .withSelector(DefaultTrafficSelector.builder()
                        .matchTcpDst(TpPort.tpPort(8080))
                        .build())
                .withTreatment(DefaultTrafficTreatment.builder()
                        .setOutput(PortNumber.P0)
                        .build())
                .makePermanent()
                .forTable(0)
                .withPriority(1)
                .forDevice(LEAF_DEVICE_ID)
                .withCookie(123)
                .build();
        FlowRule rule2 = DefaultFlowRule.builder()
                .withSelector(DefaultTrafficSelector.builder()
                        .matchIPDst(IpPrefix.valueOf("0.0.0.0/0"))
                        .build())
                .withTreatment(DefaultTrafficTreatment.builder()
                        .setEthDst(MacAddress.valueOf("10:00:01:12:23:34"))
                        .setOutput(PortNumber.portNumber(10))
                        .build())
                .makePermanent()
                .forTable(0)
                .withPriority(1)
                .forDevice(LEAF_DEVICE_ID)
                .withCookie(456)
                .build();
        return ImmutableSet.of(
                buildFlowEntry(rule1),
                buildFlowEntry(rule2)
        );
    }

    private FlowRule buildIntMetadataLocalRule(DeviceId deviceId) {
        final PiActionParam switchIdParam = new PiActionParam(
                P4InfoConstants.SWITCH_ID, NODE_SID_IPV4);

        final PiAction mirrorAction = PiAction.builder()
                .withId(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_REPORT_LOCAL)
                .withParameter(switchIdParam)
                .build();

        final TrafficTreatment mirrorTreatment = DefaultTrafficTreatment.builder()
                .piTableAction(mirrorAction)
                .build();

        final TrafficSelector mirrorSelector =
                DefaultTrafficSelector.builder().matchPi(
                        PiCriterion.builder().matchExact(
                                P4InfoConstants.HDR_INT_REPORT_TYPE,
                                INT_REPORT_TYPE_LOCAL)
                                .matchExact(
                                        P4InfoConstants.HDR_DROP_CTL,
                                        0).build())
                        .build();

        return DefaultFlowRule.builder()
                .forDevice(deviceId)
                .withSelector(mirrorSelector)
                .withTreatment(mirrorTreatment)
                .withPriority(DEFAULT_PRIORITY)
                .forTable(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_INT_METADATA)
                .fromApp(APP_ID)
                .makePermanent()
                .build();
    }

    private FlowRule buildIntMetadataDropRule(DeviceId deviceId) {
        final PiActionParam switchIdParam = new PiActionParam(
                P4InfoConstants.SWITCH_ID, NODE_SID_IPV4);

        final PiAction mirrorAction = PiAction.builder()
                .withId(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_REPORT_DROP)
                .withParameter(switchIdParam)
                .build();

        final TrafficTreatment mirrorTreatment = DefaultTrafficTreatment.builder()
                .piTableAction(mirrorAction)
                .build();

        final TrafficSelector mirrorSelector =
                DefaultTrafficSelector.builder().matchPi(
                        PiCriterion.builder().matchExact(
                                P4InfoConstants.HDR_INT_REPORT_TYPE,
                                INT_REPORT_TYPE_LOCAL).matchExact(
                                P4InfoConstants.HDR_DROP_CTL,
                                1).build())
                        .build();

        return DefaultFlowRule.builder()
                .forDevice(deviceId)
                .withSelector(mirrorSelector)
                .withTreatment(mirrorTreatment)
                .withPriority(DEFAULT_PRIORITY)
                .forTable(P4InfoConstants.FABRIC_EGRESS_INT_EGRESS_INT_METADATA)
                .fromApp(APP_ID)
                .makePermanent()
                .build();
    }

    private List<FlowRule> buildIngressDropReportTableRules(DeviceId deviceId) {
        final List<FlowRule> result = Lists.newArrayList();
        final PiActionParam switchIdParam = new PiActionParam(
                P4InfoConstants.SWITCH_ID, NODE_SID_IPV4);

        final PiAction reportDropAction = PiAction.builder()
                .withId(P4InfoConstants.FABRIC_INGRESS_INT_INGRESS_REPORT_DROP)
                .withParameter(switchIdParam)
                .build();
        final TrafficTreatment reportDropTreatment = DefaultTrafficTreatment.builder()
                .piTableAction(reportDropAction)
                .build();
        TrafficSelector reportDropSelector =
                DefaultTrafficSelector.builder()
                        .matchPi(
                                PiCriterion.builder()
                                        .matchExact(
                                                P4InfoConstants.HDR_INT_REPORT_TYPE,
                                                INT_REPORT_TYPE_LOCAL)
                                        .matchExact(
                                                P4InfoConstants.HDR_DROP_CTL,
                                                1)
                                        .matchExact(P4InfoConstants.HDR_COPY_TO_CPU,
                                                0)
                                        .build())
                        .build();
        result.add(DefaultFlowRule.builder()
                .forDevice(deviceId)
                .withSelector(reportDropSelector)
                .withTreatment(reportDropTreatment)
                .withPriority(DEFAULT_PRIORITY)
                .forTable(P4InfoConstants.FABRIC_INGRESS_INT_INGRESS_DROP_REPORT)
                .fromApp(APP_ID)
                .makePermanent()
                .build());
        reportDropSelector =
                DefaultTrafficSelector.builder()
                        .matchPi(
                                PiCriterion.builder()
                                        .matchExact(
                                                P4InfoConstants.HDR_INT_REPORT_TYPE,
                                                INT_REPORT_TYPE_LOCAL)
                                        .matchExact(
                                                P4InfoConstants.HDR_DROP_CTL,
                                                0)
                                        .matchTernary(P4InfoConstants.HDR_EGRESS_PORT_SET,
                                                0, 1)
                                        .matchTernary(P4InfoConstants.HDR_MCAST_GROUP_ID,
                                                0, 1)
                                        .matchExact(P4InfoConstants.HDR_COPY_TO_CPU,
                                                0)
                                        .build())
                        .build();
        result.add(DefaultFlowRule.builder()
                .forDevice(deviceId)
                .withSelector(reportDropSelector)
                .withTreatment(reportDropTreatment)
                .withPriority(DEFAULT_PRIORITY)
                .forTable(P4InfoConstants.FABRIC_INGRESS_INT_INGRESS_DROP_REPORT)
                .fromApp(APP_ID)
                .makePermanent()
                .build());
        return result;
    }

    private void testDefaultRecirculateRules() {
        final List<FlowRule> expectedIgPortVlanRules = Lists.newArrayList();
        final List<FlowRule> expectedEgVlanRules = Lists.newArrayList();
        final Capture<FlowRule> capturedEgVlanRule = newCapture(CaptureType.ALL);
        final Capture<FlowRule> capturedIgPortVlanRule = newCapture(CaptureType.ALL);
        final List<GroupDescription> expectedGroups = Lists.newArrayList();
        final Capture<GroupDescription> capturedGroup = newCapture(CaptureType.ALL);
        final List<FlowRule> expectedFwdClsIpRules = Lists.newArrayList();
        final Capture<FlowRule> capturedFwdClsIpRules = newCapture(CaptureType.ALL);
        final List<FlowRule> expectedFwdClsMplsRules = Lists.newArrayList();
        final Capture<FlowRule> capturedFwdClsMplsRules = newCapture(CaptureType.ALL);
        QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS.forEach((sessionId, port) -> {
            // Set up mirror sessions
            final List<GroupBucket> buckets = ImmutableList.of(
                    createCloneGroupBucket(DefaultTrafficTreatment.builder()
                            .setOutput(PortNumber.portNumber(port))
                            .build()));
            expectedGroups.add(new DefaultGroupDescription(
                    LEAF_DEVICE_ID, GroupDescription.Type.CLONE,
                    new GroupBuckets(buckets),
                    new DefaultGroupKey(KRYO.serialize(sessionId)),
                    sessionId, APP_ID));
            groupService.addGroup(capture(capturedGroup));

            // Set up ingress_port_vlan table
            final TrafficSelector igPortVlanSelector =
                    DefaultTrafficSelector.builder()
                            .add(Criteria.matchInPort(PortNumber.portNumber(port)))
                            .add(PiCriterion.builder()
                                    .matchExact(P4InfoConstants.HDR_VLAN_IS_VALID, 0)
                                    .build())
                            .build();
            final PiActionParam vlanIdParam = new PiActionParam(
                    P4InfoConstants.VLAN_ID, DEFAULT_VLAN);
            final PiAction permitWithInternalVlanAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_INGRESS_FILTERING_PERMIT_WITH_INTERNAL_VLAN)
                    .withParameter(vlanIdParam)
                    .build();
            final TrafficTreatment igPortVlanTreatment =
                    DefaultTrafficTreatment.builder()
                            .piTableAction(permitWithInternalVlanAction)
                            .build();
            expectedIgPortVlanRules.add(DefaultFlowRule.builder()
                    .withSelector(igPortVlanSelector)
                    .withTreatment(igPortVlanTreatment)
                    .forTable(P4InfoConstants.FABRIC_INGRESS_FILTERING_INGRESS_PORT_VLAN)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY)
                    .forDevice(LEAF_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());
            flowRuleService.applyFlowRules(capture(capturedIgPortVlanRule));

            // Set up egress_vlan table
            final TrafficSelector egVlanSelector =
                    DefaultTrafficSelector.builder()
                            .add(PiCriterion.builder()
                                    .matchExact(P4InfoConstants.HDR_VLAN_ID, DEFAULT_VLAN)
                                    .matchExact(P4InfoConstants.HDR_EG_PORT, port)
                                    .build())
                            .build();

            final PiAction keepVlanConfigAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_EGRESS_EGRESS_NEXT_KEEP_VLAN)
                    .build();
            final TrafficTreatment egVlanTreatment =
                    DefaultTrafficTreatment.builder()
                            .piTableAction(keepVlanConfigAction)
                            .build();
            expectedEgVlanRules.add(DefaultFlowRule.builder()
                    .withSelector(egVlanSelector)
                    .withTreatment(egVlanTreatment)
                    .forTable(P4InfoConstants.FABRIC_EGRESS_EGRESS_NEXT_EGRESS_VLAN)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY)
                    .forDevice(LEAF_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());

            flowRuleService.applyFlowRules(capture(capturedEgVlanRule));
        });
        QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS.forEach((sessionId, port) -> {
            // Fwd classifier match IPv4
            PiCriterion criterion = PiCriterion.builder()
                    .matchExact(P4InfoConstants.HDR_IP_ETH_TYPE, Ethernet.TYPE_IPV4)
                    .build();
            TrafficSelector fwdClassSel = DefaultTrafficSelector.builder()
                    .matchInPort(PortNumber.portNumber(port))
                    .matchEthDstMasked(SWITCH_MAC, MacAddress.EXACT_MASK)
                    .matchPi(criterion).build();
            PiActionParam fwdTypeParam = new PiActionParam(P4InfoConstants.FWD_TYPE, FWD_TYPE_IPV4_ROUTING);
            PiAction setFwdTypeAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_INGRESS_FILTERING_SET_FORWARDING_TYPE)
                    .withParameter(fwdTypeParam)
                    .build();
            TrafficTreatment treatment = DefaultTrafficTreatment.builder()
                    .piTableAction(setFwdTypeAction)
                    .build();
            expectedFwdClsIpRules.add(DefaultFlowRule.builder()
                    .withSelector(fwdClassSel)
                    .withTreatment(treatment)
                    .forTable(P4InfoConstants.FABRIC_INGRESS_FILTERING_FWD_CLASSIFIER)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY)
                    .forDevice(LEAF_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());
            flowRuleService.applyFlowRules(capture(capturedFwdClsIpRules));

            // Fwd classifier match MPLS + IPv4
            criterion = PiCriterion.builder()
                    .matchTernary(P4InfoConstants.HDR_ETH_TYPE,
                            EthType.EtherType.MPLS_UNICAST.ethType().toShort(),
                            ETH_TYPE_EXACT_MASK)
                    .matchExact(P4InfoConstants.HDR_IP_ETH_TYPE,
                            EthType.EtherType.IPV4.ethType().toShort())
                    .build();
            fwdClassSel = DefaultTrafficSelector.builder()
                    .matchInPort(PortNumber.portNumber(port))
                    .matchEthDstMasked(SWITCH_MAC, MacAddress.EXACT_MASK)
                    .matchPi(criterion).build();
            fwdTypeParam = new PiActionParam(P4InfoConstants.FWD_TYPE, FWD_TYPE_MPLS);
            setFwdTypeAction = PiAction.builder()
                    .withId(P4InfoConstants.FABRIC_INGRESS_FILTERING_SET_FORWARDING_TYPE)
                    .withParameter(fwdTypeParam)
                    .build();
            treatment = DefaultTrafficTreatment.builder()
                    .piTableAction(setFwdTypeAction)
                    .build();
            expectedFwdClsMplsRules.add(DefaultFlowRule.builder()
                    .withSelector(fwdClassSel)
                    .withTreatment(treatment)
                    .forTable(P4InfoConstants.FABRIC_INGRESS_FILTERING_FWD_CLASSIFIER)
                    .makePermanent()
                    .withPriority(DEFAULT_PRIORITY + 10)
                    .forDevice(LEAF_DEVICE_ID)
                    .fromApp(APP_ID)
                    .build());
            flowRuleService.applyFlowRules(capture(capturedFwdClsMplsRules));
        });
        replay(groupService, flowRuleService);
        assertTrue(intProgrammable.init());

        for (int i = 0; i < QUAD_PIPE_MIRROR_SESS_TO_RECIRC_PORTS.size(); i++) {
            GroupDescription expectGroup = expectedGroups.get(i);
            GroupDescription actualGroup = capturedGroup.getValues().get(i);
            FlowRule expectIgPortVlanRule = expectedIgPortVlanRules.get(i);
            FlowRule actualIgPortVlanRule = capturedIgPortVlanRule.getValues().get(i);
            FlowRule expectEgVlanRule = expectedEgVlanRules.get(i);
            FlowRule actualEgVlanRule = capturedEgVlanRule.getValues().get(i);
            FlowRule expectedFwdClsIpRule = expectedFwdClsIpRules.get(i);
            FlowRule actualFwdClsIpRule = capturedFwdClsIpRules.getValues().get(i);
            FlowRule expectedFwdClsMplsRule = expectedFwdClsMplsRules.get(i);
            FlowRule actualFwdClsMplsRule = capturedFwdClsMplsRules.getValues().get(i);
            assertEquals(expectGroup, actualGroup);
            assertTrue(expectIgPortVlanRule.exactMatch(actualIgPortVlanRule));
            assertTrue(expectEgVlanRule.exactMatch(actualEgVlanRule));
            assertTrue(expectedFwdClsIpRule.exactMatch(actualFwdClsIpRule));
            assertTrue(expectedFwdClsMplsRule.exactMatch(actualFwdClsMplsRule));
        }

        verify(groupService, flowRuleService);
        reset(groupService, flowRuleService);
    }
}
