// Copyright 2020-present Open Networking Foundation
// SPDX-License-Identifier: Apache-2.0
package org.stratumproject.fabric.tna.behaviour.upf;

import com.google.common.collect.Sets;
import org.onosproject.core.ApplicationId;
import org.onosproject.net.DeviceId;
import org.onosproject.net.flow.DefaultFlowEntry;
import org.onosproject.net.flow.FlowEntry;
import org.onosproject.net.flow.FlowRule;
import org.onosproject.net.flow.FlowRuleOperations;
import org.onosproject.net.flow.FlowRuleServiceAdapter;

import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.stream.Collectors;

/**
 * Created by nikcheerla on 7/20/15.
 */

public class MockFlowRuleService extends FlowRuleServiceAdapter {

    final Set<FlowRule> flows = Sets.newHashSet();
    boolean success;

    int errorFlow = -1;

    public void setErrorFlow(int errorFlow) {
        this.errorFlow = errorFlow;
    }

    public void setFuture(boolean success) {
        this.success = success;
    }

    @Override
    public void apply(FlowRuleOperations ops) {
        AtomicBoolean thisSuccess = new AtomicBoolean(success);
        ops.stages().forEach(stage -> stage.forEach(flow -> {
            if (errorFlow == flow.rule().id().value()) {
                thisSuccess.set(false);
            } else {
                switch (flow.type()) {
                    case ADD:
                    case MODIFY: //TODO is this the right behavior for modify?
                        ((DefaultFlowEntry) flow.rule()).setState(FlowEntry.FlowEntryState.ADDED);
                        flows.add(flow.rule());
                        break;
                    case REMOVE:
                        // Remove and add in REMOVED state
                        flows.remove(flow.rule());
                        ((DefaultFlowEntry) flow.rule()).setState(FlowEntry.FlowEntryState.REMOVED);
                        flows.add(flow.rule());
                        break;
                    default:
                        break;
                }
            }
        }));
        if (thisSuccess.get()) {
            ops.callback().onSuccess(ops);
        } else {
            ops.callback().onError(ops);
        }
    }

    @Override
    public int getFlowRuleCount() {
        return flows.size();
    }

    @Override
    public Iterable<FlowEntry> getFlowEntries(DeviceId deviceId) {
        return flows.stream()
                .filter(flow -> flow.deviceId().equals(deviceId))
                .map(DefaultFlowEntry::new)
                .collect(Collectors.toList());
    }

    @Override
    public void applyFlowRules(FlowRule... flowRules) {
        for (FlowRule flow : flowRules) {
            flows.add(flow);
        }
    }

    @Override
    public void removeFlowRules(FlowRule... flowRules) {
        for (FlowRule flow : flowRules) {
            flows.remove(flow);
        }
    }

    @Override
    public Iterable<FlowRule> getFlowRulesByGroupId(ApplicationId appId, short groupId) {
        return flows.stream()
                .filter(flow -> flow.appId() == appId.id() && flow.groupId().id() == groupId)
                .collect(Collectors.toList());
    }

    @Override
    public Iterable<FlowEntry> getFlowEntriesById(ApplicationId id) {
        return flows.stream()
                .filter(flow -> flow.appId() == id.id())
                .map(DefaultFlowEntry::new)
                .collect(Collectors.toList());
    }
}


