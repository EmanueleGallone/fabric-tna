// Copyright 2020-present Open Networking Foundation
// SPDX-License-Identifier: Apache-2.0
package org.stratumproject.fabric.tna.behaviour.upf;

import org.apache.commons.lang3.tuple.Pair;
import org.junit.Test;
import org.onosproject.net.behaviour.upf.UpfApplication;
import org.onosproject.net.behaviour.upf.UpfGtpTunnelPeer;
import org.onosproject.net.behaviour.upf.UpfInterface;
import org.onosproject.net.behaviour.upf.UpfMeter;
import org.onosproject.net.behaviour.upf.UpfProgrammableException;
import org.onosproject.net.behaviour.upf.UpfSessionDownlink;
import org.onosproject.net.behaviour.upf.UpfSessionUplink;
import org.onosproject.net.behaviour.upf.UpfTerminationDownlink;
import org.onosproject.net.behaviour.upf.UpfTerminationUplink;
import org.onosproject.net.flow.FlowRule;
import org.onosproject.net.meter.MeterRequest;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;

public class FabricUpfTranslatorTest {

    private final FabricUpfTranslator upfTranslator = new FabricUpfTranslator();

    @Test
    public void fabricEntryToGtpTunnelPeerTest() {
        UpfGtpTunnelPeer translated;
        UpfGtpTunnelPeer expected = TestUpfConstants.GTP_TUNNEL_PEER;
        try {
            translated = upfTranslator.fabricEntryToGtpTunnelPeer(TestUpfConstants.FABRIC_EGRESS_GTP_TUNNEL_PEER);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric GTP tunnel peer should correctly translate to abstract GTP tunnel peer without error",
                       false);
            return;
        }
        assertThat(translated, equalTo(expected));
    }

    @Test
    public void fabricEntryToUplinkUeSessionTest() {
        UpfSessionUplink translated;
        UpfSessionUplink expected = TestUpfConstants.UPLINK_UE_SESSION;
        try {
            translated = upfTranslator.fabricEntryToUeSessionUplink(TestUpfConstants.FABRIC_UPLINK_UE_SESSION);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric uplink UE session should correctly translate to abstract UE session without error",
                       false);
            return;
        }
        assertThat(translated, equalTo(expected));
    }

    @Test
    public void fabricEntryToDownlinkUeSessionTest() {
        UpfSessionDownlink translated;
        UpfSessionDownlink expected = TestUpfConstants.DOWNLINK_UE_SESSION;
        try {
            translated = upfTranslator.fabricEntryToUeSessionDownlink(TestUpfConstants.FABRIC_DOWNLINK_UE_SESSION);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric downlink UE session should correctly translate to abstract UE session without error",
                       false);
            return;
        }
        assertThat(translated, equalTo(expected));
    }

    @Test
    public void fabricEntryToDownlinkUeSessionDbufTest() {
        UpfSessionDownlink translated;
        UpfSessionDownlink expected = TestUpfConstants.DOWNLINK_UE_SESSION_DBUF;
        try {
            translated = upfTranslator.fabricEntryToUeSessionDownlink(TestUpfConstants.FABRIC_DOWNLINK_UE_SESSION_DBUF);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric downlink DBUF UE session should correctly " +
                               "translate to abstract UE session without error",
                       false);
            return;
        }
        assertThat("Translated UE Session should be buffering.",
                   translated.needsBuffering());
        assertThat(translated, equalTo(expected));
    }

    @Test
    public void fabricEntryToUplinkUpfTerminationTest() {
        UpfTerminationUplink translatedUpfTerminationRule;
        UpfTerminationUplink expected = TestUpfConstants.UPLINK_UPF_TERMINATION;
        try {
            translatedUpfTerminationRule = upfTranslator
                    .fabricEntryToUpfTerminationUplink(TestUpfConstants.FABRIC_UPLINK_UPF_TERMINATION);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric uplink UPF termination rule should correctly " +
                               "translate to abstract UPF termination without error",
                       false);
            return;
        }
        assertThat(translatedUpfTerminationRule, equalTo(expected));
    }

    @Test
    public void fabricEntryToUplinkUpfTerminationNoTcTest() {
        UpfTerminationUplink translatedUpfTerminationRule;
        UpfTerminationUplink expected = TestUpfConstants.UPLINK_UPF_TERMINATION_NO_TC;
        try {
            translatedUpfTerminationRule = upfTranslator
                    .fabricEntryToUpfTerminationUplink(TestUpfConstants.FABRIC_UPLINK_UPF_TERMINATION_NO_TC);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric uplink UPF termination rule should correctly " +
                               "translate to abstract UPF termination without error",
                       false);
            return;
        }
        assertThat(translatedUpfTerminationRule, equalTo(expected));
    }

    @Test
    public void fabricEntryToUplinkUpfTerminationDropTest() {
        UpfTerminationUplink translatedUpfTerminationRule;
        UpfTerminationUplink expected = TestUpfConstants.UPLINK_UPF_TERMINATION_DROP;
        try {
            translatedUpfTerminationRule = upfTranslator
                    .fabricEntryToUpfTerminationUplink(TestUpfConstants.FABRIC_UPLINK_UPF_TERMINATION_DROP);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric uplink UPF termination rule should correctly " +
                               "translate to abstract UPF termination without error",
                       false);
            return;
        }
        assertThat(translatedUpfTerminationRule, equalTo(expected));
    }

    @Test
    public void fabricEntryToDownlinkUpfTerminationTest() {
        UpfTerminationDownlink translatedUpfTerminationRule;
        UpfTerminationDownlink expected = TestUpfConstants.DOWNLINK_UPF_TERMINATION;
        try {
            translatedUpfTerminationRule = upfTranslator
                    .fabricEntryToUpfTerminationDownlink(TestUpfConstants.FABRIC_DOWNLINK_UPF_TERMINATION);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric downlink UPF termination rule should correctly " +
                               "translate to abstract UPF termination without error",
                       false);
            return;
        }
        assertThat(translatedUpfTerminationRule, equalTo(expected));
    }

    @Test
    public void fabricEntryToDownlinkUpfTerminationNoTcTest() {
        UpfTerminationDownlink translatedUpfTerminationRule;
        UpfTerminationDownlink expected = TestUpfConstants.DOWNLINK_UPF_TERMINATION_NO_TC;
        try {
            translatedUpfTerminationRule = upfTranslator
                    .fabricEntryToUpfTerminationDownlink(TestUpfConstants.FABRIC_DOWNLINK_UPF_TERMINATION_NO_TC);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric downlink UPF termination rule should correctly " +
                               "translate to abstract UPF termination without error",
                       false);
            return;
        }
        assertThat(translatedUpfTerminationRule, equalTo(expected));
    }

    @Test
    public void fabricEntryToDownlinkUpfTerminationDropTest() {
        UpfTerminationDownlink translatedUpfTerminationRule;
        UpfTerminationDownlink expected = TestUpfConstants.DOWNLINK_UPF_TERMINATION_DROP;
        try {
            translatedUpfTerminationRule = upfTranslator
                    .fabricEntryToUpfTerminationDownlink(TestUpfConstants.FABRIC_DOWNLINK_UPF_TERMINATION_DROP);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric downlink UPF termination rule should correctly " +
                               "translate to abstract UPF termination without error",
                       false);
            return;
        }
        assertThat(translatedUpfTerminationRule, equalTo(expected));
    }

    @Test
    public void fabricEntryToUplinkInterfaceTest() {
        UpfInterface translatedInterface;
        UpfInterface expectedInterface = TestUpfConstants.UPLINK_INTERFACE;
        try {
            translatedInterface = upfTranslator.fabricEntryToInterface(TestUpfConstants.FABRIC_UPLINK_INTERFACE);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric uplink interface should correctly translate to abstract interface without error",
                       false);
            return;
        }
        assertThat("Translated interface should be uplink.", translatedInterface.isAccess());
        assertThat(translatedInterface, equalTo(expectedInterface));
    }

    @Test
    public void fabricEntryToDownlinkInterfaceTest() {
        UpfInterface translatedInterface;
        UpfInterface expectedInterface = TestUpfConstants.DOWNLINK_INTERFACE;
        try {
            translatedInterface = upfTranslator.fabricEntryToInterface(TestUpfConstants.FABRIC_DOWNLINK_INTERFACE);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric downlink interface should correctly translate to abstract interface without error",
                       false);
            return;
        }
        assertThat("Translated interface should be downlink.", translatedInterface.isCore());
        assertThat(translatedInterface, equalTo(expectedInterface));
    }

    @Test
    public void fabricEntryToUpfApplicationTest() {
        UpfApplication translatedInterface;
        UpfApplication expectedInterface = TestUpfConstants.APPLICATION_FILTERING;
        try {
            translatedInterface = upfTranslator.fabricEntryToUpfApplication(
                    TestUpfConstants.FABRIC_APPLICATION_FILTERING);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric application filtering should correctly translate to abstract application without error",
                       false);
            return;
        }
        assertThat(translatedInterface, equalTo(expectedInterface));
    }

    @Test
    public void fabricMeterToUpfSessionMeterTest() {
        UpfMeter translatedMeter;
        UpfMeter expectedMeter = TestUpfConstants.SESSION_METER;
        try {
            translatedMeter = upfTranslator.fabricMeterToUpfSessionMeter(
                    TestUpfConstants.FABRIC_SESSION_METER);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric session meter should correctly translate to abstract UPF meter without error",
                       false);
            return;
        }
        assertThat(translatedMeter, equalTo(expectedMeter));
    }

    @Test
    public void fabricMeterToUpfAppMeterTest() {
        UpfMeter translatedMeter;
        UpfMeter expectedMeter = TestUpfConstants.APP_METER;
        try {
            translatedMeter = upfTranslator.fabricMeterToUpfAppMeter(
                    TestUpfConstants.FABRIC_APP_METER);
        } catch (UpfProgrammableException e) {
            assertThat("Fabric application meter should correctly " +
                               "translate to abstract UPF meter without error",
                       false);
            return;
        }
        assertThat(translatedMeter, equalTo(expectedMeter));

        // THIS SHOULD NEVER BE A CASE FOR US, WE CAN'T READ RESET METER!!!
//        UpfMeter expectedResetMeter = TestUpfConstants.APP_METER_RESET;
//        try {
//            translatedMeter = upfTranslator.fabricMeterToUpfAppMeter(
//                    TestUpfConstants.FABRIC_APP_METER_RESET);
//        } catch (UpfProgrammableException e) {
//            assertThat("Fabric application reset meter should correctly
//            translate to abstract UPF reset meter without error",
//                       false);
//            return;
//        }
//        assertThat(translatedMeter, equalTo(expectedResetMeter));
    }
    // -------------------------------------------------------------------------
    @Test
    public void uplinkInterfaceToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_UPLINK_INTERFACE;
        try {
            translatedRule = upfTranslator.interfaceToFabricEntry(TestUpfConstants.UPLINK_INTERFACE,
                                                                  TestUpfConstants.DEVICE_ID,
                                                                  TestUpfConstants.APP_ID,
                                                                  TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract uplink interface should correctly translate to Fabric interface without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
    }

    @Test
    public void downlinkInterfaceToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_DOWNLINK_INTERFACE;
        try {
            translatedRule = upfTranslator.interfaceToFabricEntry(TestUpfConstants.DOWNLINK_INTERFACE,
                                                                  TestUpfConstants.DEVICE_ID,
                                                                  TestUpfConstants.APP_ID,
                                                                  TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract downlink interface should correctly translate to Fabric interface without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
    }

    @Test
    public void gtpTunnelPeerToFabricEntryTest() {
        Pair<FlowRule, FlowRule> translatedRule;
        Pair<FlowRule, FlowRule> expected = Pair.of(
                TestUpfConstants.FABRIC_INGRESS_GTP_TUNNEL_PEER,
                TestUpfConstants.FABRIC_EGRESS_GTP_TUNNEL_PEER);
        try {
            translatedRule = upfTranslator.gtpTunnelPeerToFabricEntry(
                    TestUpfConstants.GTP_TUNNEL_PEER,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract GTP tunnel peer should correctly translate to Fabric flow rules without error",
                       false);
            return;
        }
        assertThat(translatedRule.getLeft(), equalTo(expected.getLeft()));
        assertThat(translatedRule.getLeft().treatment(), equalTo(expected.getLeft().treatment()));
        assertThat(translatedRule.getRight(), equalTo(expected.getRight()));
        assertThat(translatedRule.getRight().treatment(), equalTo(expected.getRight().treatment()));
    }

    @Test
    public void uplinkUeSessionToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_UPLINK_UE_SESSION;
        try {
            translatedRule = upfTranslator.sessionUplinkToFabricEntry(
                    TestUpfConstants.UPLINK_UE_SESSION,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract uplink UE session should correctly " +
                               "translate to Fabric UE session without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void downlinkUeSessionToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_DOWNLINK_UE_SESSION;
        try {
            translatedRule = upfTranslator.sessionDownlinkToFabricEntry(
                    TestUpfConstants.DOWNLINK_UE_SESSION,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract downlink UE session should correctly " +
                               "translate to Fabric UE session without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void downlinkUeSessionDbufToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_DOWNLINK_UE_SESSION_DBUF;
        try {
            translatedRule = upfTranslator.sessionDownlinkToFabricEntry(
                    TestUpfConstants.DOWNLINK_UE_SESSION_DBUF,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract downlink DBUF UE session should correctly " +
                               "translate to Fabric UE session without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void uplinkUpfTerminationToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_UPLINK_UPF_TERMINATION;
        try {
            translatedRule = upfTranslator.upfTerminationUplinkToFabricEntry(
                    TestUpfConstants.UPLINK_UPF_TERMINATION,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract uplink UPF Termination should correctly " +
                               "translate to Fabric UPF Termination without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void uplinkUpfTerminationNoTcToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_UPLINK_UPF_TERMINATION_NO_TC;
        try {
            translatedRule = upfTranslator.upfTerminationUplinkToFabricEntry(
                    TestUpfConstants.UPLINK_UPF_TERMINATION_NO_TC,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract uplink UPF Termination should correctly " +
                               "translate to Fabric UPF Termination without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void uplinkUpfTerminationDropToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_UPLINK_UPF_TERMINATION_DROP;
        try {
            translatedRule = upfTranslator.upfTerminationUplinkToFabricEntry(
                    TestUpfConstants.UPLINK_UPF_TERMINATION_DROP,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract uplink UPF Termination should correctly " +
                               "translate to Fabric UPF Termination without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void downlinkUpfTerminationToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_DOWNLINK_UPF_TERMINATION;
        try {
            translatedRule = upfTranslator.upfTerminationDownlinkToFabricEntry(
                    TestUpfConstants.DOWNLINK_UPF_TERMINATION,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract downlink UPF Termination should correctly " +
                               "translate to Fabric UPF Termination without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void upfApplicationToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_APPLICATION_FILTERING;
        try {
            translatedRule = upfTranslator.upfApplicationToFabricEntry(
                    TestUpfConstants.APPLICATION_FILTERING,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract application should correctly translate " +
                               "to Fabric application filtering without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void downlinkUpfTerminationNoTcToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_DOWNLINK_UPF_TERMINATION_NO_TC;
        try {
            translatedRule = upfTranslator.upfTerminationDownlinkToFabricEntry(
                    TestUpfConstants.DOWNLINK_UPF_TERMINATION_NO_TC,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract downlink UPF Termination should correctly " +
                               "translate to Fabric UPF Termination without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void downlinkUpfTerminationDropToFabricEntryTest() {
        FlowRule translatedRule;
        FlowRule expectedRule = TestUpfConstants.FABRIC_DOWNLINK_UPF_TERMINATION_DROP;
        try {
            translatedRule = upfTranslator.upfTerminationDownlinkToFabricEntry(
                    TestUpfConstants.DOWNLINK_UPF_TERMINATION_DROP,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID,
                    TestUpfConstants.DEFAULT_PRIORITY);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract downlink UPF Termination should correctly " +
                               "translate to Fabric UPF Termination without error",
                       false);
            return;
        }
        assertThat(translatedRule, equalTo(expectedRule));
        assertThat(translatedRule.treatment(), equalTo(expectedRule.treatment()));
    }

    @Test
    public void sessionUpfMeterToFabricMeterTest() {
        MeterRequest translatedMeter;
        MeterRequest expectedMeter = TestUpfConstants.FABRIC_SESSION_METER_REQUEST;
        try {
            translatedMeter = upfTranslator.upfMeterToFabricMeter(
                    TestUpfConstants.SESSION_METER,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract session UPF meter should correctly " +
                               "translate to Fabric UPF session meter without error",
                       false);
            return;
        }
        // TODO: should we implement equals for DefaultMeterRequest?
        assertThat(translatedMeter.appId(), equalTo(expectedMeter.appId()));
        assertThat(translatedMeter.deviceId(), equalTo(expectedMeter.deviceId()));
        assertThat(translatedMeter.isBurst(), equalTo(expectedMeter.isBurst()));
        assertThat(translatedMeter.scope(), equalTo(expectedMeter.scope()));
        assertThat(translatedMeter.index(), equalTo(expectedMeter.index()));
        assertThat(translatedMeter.bands(), equalTo(expectedMeter.bands()));
    }

    @Test
    public void sessionUpfMeterResetToFabricMeterResetTest() {
        MeterRequest translatedMeter;
        MeterRequest expectedMeter = TestUpfConstants.FABRIC_SESSION_METER_RESET_REQUEST;
        try {
            translatedMeter = upfTranslator.upfMeterToFabricMeter(
                    TestUpfConstants.SESSION_METER_RESET,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract session UPF meter should correctly " +
                               "translate to Fabric UPF session meter without error",
                       false);
            return;
        }
        // TODO: should we implement equals for DefaultMeterRequest?
        assertThat(translatedMeter.appId(), equalTo(expectedMeter.appId()));
        assertThat(translatedMeter.deviceId(), equalTo(expectedMeter.deviceId()));
        assertThat(translatedMeter.isBurst(), equalTo(expectedMeter.isBurst()));
        assertThat(translatedMeter.scope(), equalTo(expectedMeter.scope()));
        assertThat(translatedMeter.index(), equalTo(expectedMeter.index()));
        assertThat(translatedMeter.bands(), equalTo(expectedMeter.bands()));
    }

    @Test
    public void appUpfMeterToFabricMeterTest() {
        MeterRequest translatedMeter;
        MeterRequest expectedMeter = TestUpfConstants.FABRIC_APP_METER_REQUEST;
        try {
            translatedMeter = upfTranslator.upfMeterToFabricMeter(
                    TestUpfConstants.APP_METER,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract app UPF meter should correctly " +
                               "translate to Fabric UPF app meter without error",
                       false);
            return;
        }
        // TODO: should we implement equals for DefaultMeterRequest?
        assertThat(translatedMeter.appId(), equalTo(expectedMeter.appId()));
        assertThat(translatedMeter.deviceId(), equalTo(expectedMeter.deviceId()));
        assertThat(translatedMeter.isBurst(), equalTo(expectedMeter.isBurst()));
        assertThat(translatedMeter.scope(), equalTo(expectedMeter.scope()));
        assertThat(translatedMeter.index(), equalTo(expectedMeter.index()));
        assertThat(translatedMeter.bands(), equalTo(expectedMeter.bands()));
    }

    @Test
    public void appUpfMeterResetToFabricMeterTest() {
        MeterRequest translatedMeter;
        MeterRequest expectedMeter = TestUpfConstants.FABRIC_APP_METER_RESET_REQUEST;
        try {
            translatedMeter = upfTranslator.upfMeterToFabricMeter(
                    TestUpfConstants.APP_METER_RESET,
                    TestUpfConstants.DEVICE_ID,
                    TestUpfConstants.APP_ID);
        } catch (UpfProgrammableException e) {
            assertThat("Abstract app UPF meter should correctly " +
                               "translate to Fabric UPF app meter without error",
                       false);
            return;
        }
        // TODO: should we implement equals for DefaultMeterRequest?
        assertThat(translatedMeter.appId(), equalTo(expectedMeter.appId()));
        assertThat(translatedMeter.deviceId(), equalTo(expectedMeter.deviceId()));
        assertThat(translatedMeter.isBurst(), equalTo(expectedMeter.isBurst()));
        assertThat(translatedMeter.scope(), equalTo(expectedMeter.scope()));
        assertThat(translatedMeter.index(), equalTo(expectedMeter.index()));
        assertThat(translatedMeter.bands(), equalTo(expectedMeter.bands()));
    }
}
