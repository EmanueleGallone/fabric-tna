
// Copyright 2021-present Open Networking Foundation
// SPDX-License-Identifier: Apache-2.0

#ifndef __UPF__
#define __UPF__

control UpfIngress(
        /* Fabric.p4 */
        inout ingress_headers_t          hdr,
        inout fabric_ingress_metadata_t  fabric_md,
        inout standard_metadata_t        standard_md,
        inout bool                       do_upf_uplink_recirc,
        inout bit<1>                     drop_ctl) {

    //========================//
    //===== Misc Things ======//
    //========================//

    counter(MAX_UPF_COUNTERS, CounterType.packets_and_bytes) terminations_counter;

    meter(MAX_SESSION_METERS, MeterType.bytes) session_meter;
    meter(MAX_APP_METERS, MeterType.bytes) app_meter;

    bool is_uplink = false;
    bool term_hit = false;
    bool sess_hit = false;
    bit<32> app_ipv4_addr = 0;
    l4_port_t app_l4_port = 0;
    bit<8> app_ip_proto = 0;
    bit<8> internal_app_id = DEFAULT_APP_ID;
    ue_session_id_t ue_session_id = 0;

    session_meter_idx_t session_meter_idx_internal = DEFAULT_SESSION_METER_IDX;
    app_meter_idx_t app_meter_idx_internal = DEFAULT_APP_METER_IDX;

    @hidden
    action _drop_common() {
        drop_ctl = 1;
        fabric_md.skip_forwarding = true;
        fabric_md.skip_next = true;
    }

    @hidden
    action _term_hit(upf_ctr_idx_t ctr_id) {
        fabric_md.bridged.upf.upf_ctr_id = ctr_id;
        term_hit = true;
    }

    @hidden
    action _set_field_encap(teid_t  teid,
                            // QFI should always equal 0 for 4G flows
                            bit<6>  qfi) {
        fabric_md.bridged.upf.needs_gtpu_encap = true;
        fabric_md.bridged.upf.teid = teid;
        fabric_md.bridged.upf.qfi = qfi;
    }

    @hidden
    action _gtpu_decap() {
        fabric_md.bridged.base.ip_eth_type = ETHERTYPE_IPV4;
        fabric_md.routing_ipv4_dst = hdr.inner_ipv4.dst_addr;
        // Move GTPU and inner L3 headers out
        hdr.ipv4 = hdr.inner_ipv4;
        hdr.inner_ipv4.setInvalid();
        hdr.udp = hdr.inner_udp;
        hdr.inner_udp.setInvalid();
        hdr.tcp = hdr.inner_tcp;
        hdr.inner_tcp.setInvalid();
        hdr.icmp = hdr.inner_icmp;
        hdr.inner_icmp.setInvalid();
        hdr.gtpu.setInvalid();
        hdr.gtpu_options.setInvalid();
        hdr.gtpu_ext_psc.setInvalid();
        fabric_md.bridged.base.encap_presence = EncapPresence.NONE;
    }


    //=============================//
    //===== Interface Tables ======//
    //=============================//

    @hidden
    action _iface_common(slice_id_t slice_id) {
        fabric_md.bridged.upf.skip_upf = false;
        fabric_md.is_upf_hit = true;
        fabric_md.upf_slice_id = slice_id;
    }

    action iface_access(slice_id_t slice_id) {
        _iface_common(slice_id);
    }

    action iface_core(slice_id_t slice_id) {
        _iface_common(slice_id);
    }

    action iface_dbuf(slice_id_t slice_id) {
        _iface_common(slice_id);
        _gtpu_decap();
    }

    action iface_miss() {
        fabric_md.bridged.upf.skip_upf = true;
    }

    table interfaces {
        key = {
            // Outermost IPv4 header
            hdr.ipv4.dst_addr  : lpm    @name("ipv4_dst_addr");
            // gtpu extracted only if msgtype == GTPU_GPDU (see parser)
            hdr.gtpu.isValid() : exact  @name("gtpu_is_valid");
        }
        actions = {
            iface_access;
            iface_core;
            iface_dbuf;
            @defaultonly iface_miss;
        }
        const default_action = iface_miss();
        const size = NUM_UPF_INTERFACES;
    }

    //===============================//
    //===== UE Sessions Tables ======//
    //===============================//

    action set_uplink_session_miss() {
        _drop_common();
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_UL_SESSION_MISS;
#endif // WITH_INT
    }

    action set_uplink_session_drop() {
        sess_hit = true;
        _drop_common();
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_UL_SESSION_DROP;
#endif // WITH_INT
    }

    action set_downlink_session_miss() {
        _drop_common();
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_DL_SESSION_MISS;
#endif // WITH_INT
    }

    action set_downlink_session_drop() {
        sess_hit = true;
        _drop_common();
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_DL_SESSION_DROP;
#endif // WITH_INT
    }

    action set_downlink_session(tun_peer_id_t tun_peer_id, session_meter_idx_t session_meter_idx) {
        sess_hit = true;
        // Set UE IP address.
        ue_session_id = fabric_md.routing_ipv4_dst;
        session_meter_idx_internal = session_meter_idx;
        fabric_md.bridged.upf.tun_peer_id = tun_peer_id;
    }

    action set_downlink_session_buf(tun_peer_id_t tun_peer_id, session_meter_idx_t session_meter_idx) {
        sess_hit = true;
        // Set UE IP address.
        ue_session_id = fabric_md.routing_ipv4_dst;
        session_meter_idx_internal = session_meter_idx;
        fabric_md.bridged.upf.tun_peer_id = tun_peer_id;
        // Sending to dbuf means buffering, while the egress counter is used only
        // to keep track of packets effectively sent to UEs. We will update it
        // when draining from dbuf.
        fabric_md.bridged.upf.skip_egress_upf_ctr = true;
    }

    action set_downlink_session_buf_drop() {
        sess_hit = true;
        // Set UE IP address, so we can match on the terminations table and
        // count packets in the ingress UPF counter.
        ue_session_id = fabric_md.routing_ipv4_dst;
        _drop_common();
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_DL_SESSION_DROP_BUFF;
#endif // WITH_INT
    }

    action set_uplink_session(session_meter_idx_t session_meter_idx) {
        sess_hit = true;
        // Set UE IP address.
        ue_session_id = fabric_md.lkp.ipv4_src;
        session_meter_idx_internal = session_meter_idx;
        // implicit decap
        _gtpu_decap();
    }

    table downlink_sessions {
        key = {
            fabric_md.routing_ipv4_dst : exact @name("ue_addr");
        }
        actions = {
            set_downlink_session;
            set_downlink_session_buf;
            set_downlink_session_buf_drop;
            set_downlink_session_drop;
            @defaultonly set_downlink_session_miss;
        }
        size = NUM_UES;
        const default_action = set_downlink_session_miss();
    }

    table uplink_sessions {
        key = {
            hdr.ipv4.dst_addr : exact @name("tunnel_ipv4_dst");
            hdr.gtpu.teid     : exact @name("teid");
        }
        actions = {
            set_uplink_session;
            set_uplink_session_drop;
            @defaultonly set_uplink_session_miss;
        }
        size = NUM_UPLINK_SESSIONS;
        const default_action = set_uplink_session_miss();
    }

    //=============================//
    //===== UPF Terminations ======//
    //=============================//

    action uplink_drop_miss() {
        _drop_common();
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_UL_TERMINATION_MISS;
#endif // WITH_INT
    }

    action downlink_drop_miss() {
        _drop_common();
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_DL_TERMINATION_MISS;
#endif // WITH_INT
    }

    action uplink_drop(upf_ctr_idx_t ctr_id) {
        _drop_common();
        _term_hit(ctr_id);
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_UL_TERMINATION_DROP;
#endif // WITH_INT
    }

    action downlink_drop(upf_ctr_idx_t ctr_id) {
        _drop_common();
        _term_hit(ctr_id);
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_DL_TERMINATION_DROP;
#endif // WITH_INT
    }

    action app_fwd(upf_ctr_idx_t ctr_id,
                   tc_t tc,
                   app_meter_idx_t app_meter_idx) {
        _term_hit(ctr_id);
        fabric_md.upf_tc = tc;
        app_meter_idx_internal = app_meter_idx;
        fabric_md.tc_unknown = false;
    }

    action app_fwd_no_tc(upf_ctr_idx_t ctr_id, app_meter_idx_t app_meter_idx) {
        _term_hit(ctr_id);
        fabric_md.tc_unknown = true;
        app_meter_idx_internal = app_meter_idx;
    }

    action downlink_fwd_encap(upf_ctr_idx_t ctr_id,
                              tc_t         tc,
                              teid_t       teid,
                              // QFI should always equal 0 for 4G flows
                              bit<6>       qfi,
                              app_meter_idx_t app_meter_idx) {
        app_fwd(ctr_id, tc, app_meter_idx);
        _set_field_encap(teid, qfi);
    }

    action downlink_fwd_encap_no_tc(upf_ctr_idx_t ctr_id,
                                    teid_t       teid,
                                    // QFI should always equal 0 for 4G flows
                                    bit<6>       qfi,
                                    app_meter_idx_t app_meter_idx) {
        app_fwd_no_tc(ctr_id, app_meter_idx);
        _set_field_encap(teid, qfi);
    }

    table uplink_terminations {
        key = {
            ue_session_id             : exact @name("ue_session_id");
            internal_app_id           : exact @name("app_id");
        }

        actions = {
            app_fwd;
            app_fwd_no_tc;
            uplink_drop;
            @defaultonly uplink_drop_miss;
        }
        const default_action = uplink_drop_miss();
        const size = NUM_UPF_TERMINATIONS;
    }

    table downlink_terminations {
        key = {
            ue_session_id             : exact @name("ue_session_id");
            internal_app_id           : exact @name("app_id");
        }
        actions = {
            downlink_fwd_encap;
            downlink_fwd_encap_no_tc;
            downlink_drop;
            @defaultonly downlink_drop_miss;
        }
        const default_action = downlink_drop_miss();
        const size = NUM_UPF_TERMINATIONS;
    }

    //=================================//
    //===== Ingress Tunnel Peers ======//
    //=================================//

    action set_routing_ipv4_dst(ipv4_addr_t tun_dst_addr) {
        fabric_md.routing_ipv4_dst = tun_dst_addr;
    }

    table ig_tunnel_peers {
        key = {
            fabric_md.bridged.upf.tun_peer_id : exact @name("tun_peer_id");
        }

        actions = {
            set_routing_ipv4_dst;
            @defaultonly nop;
        }
        const default_action = nop();
        const size = MAX_GTP_TUNNEL_PEERS;
    }

    //=================================//
    //===== Application Filtering =====//
    //=================================//
    action set_app_id(bit<8> app_id) {
        internal_app_id = app_id;
    }

    table applications {
        key  = {
            fabric_md.upf_slice_id : exact   @name("slice_id");
            app_ipv4_addr           : lpm     @name("app_ipv4_addr");
            app_l4_port             : range   @name("app_l4_port");
            app_ip_proto            : ternary @name("app_ip_proto");
        }
        actions = {
            set_app_id;
            @defaultonly nop;
        }
        const default_action = nop();
        size = MAX_APPLICATIONS;
    }

    //=================================//
    //===== Uplink Recirculation ======//
    //=================================//

    direct_counter(CounterType.packets) recirc_stats;

    action recirc_allow() {
        // Recirculation in bmv2 is obtained via recirculate() primitive, invoked in the egress pipeline.
        // We set the egress_spec to the FAKE_V1MODEL_RECIRC_PORT, that is intended also as a recirculation port.
        // For more info on FAKE_V1MODEL_RECIRC_PORT, see v1model/define_v1model.p4
        standard_md.egress_spec = FAKE_V1MODEL_RECIRC_PORT;
        fabric_md.bridged.base.vlan_id = DEFAULT_VLAN_ID;
        do_upf_uplink_recirc = true;
        fabric_md.egress_port_set = true;
        fabric_md.skip_forwarding = true;
        fabric_md.skip_next = true;
        recirc_stats.count();
    }

    action recirc_deny() {
#ifdef WITH_INT
        fabric_md.bridged.int_bmd.drop_reason = IntDropReason_t.DROP_REASON_UPF_UPLINK_RECIRC_DENY;
#endif // WITH_INT
        do_upf_uplink_recirc = false;
        fabric_md.skip_forwarding = true;
        fabric_md.skip_next = true;
        recirc_stats.count();
    }

    action recirc_miss() {
        recirc_stats.count();
    }

    // Allows or denies recirculation of uplink packets for UE-to-UE communication.
    // Should be called after GTP decap.
    table uplink_recirc_rules {
        key = {
            fabric_md.lkp.ipv4_src : ternary @name("ipv4_src");
            fabric_md.lkp.ipv4_dst : ternary @name("ipv4_dst");
        }
        actions = {
            recirc_allow;
            recirc_deny;
            @defaultonly recirc_miss;
        }
        const default_action = recirc_miss;
        size = MAX_UPLINK_RECIRC_RULES;
        counters = recirc_stats;
    }

    //========================//
    //===== Apply Block ======//
    //========================//
    apply {
        if (hdr.ipv4.isValid()) {
            switch(interfaces.apply().action_run) {
                iface_access: {
                    is_uplink = true;
                    app_ipv4_addr = fabric_md.lkp.ipv4_dst;
                    app_l4_port = fabric_md.lkp.l4_dport;
                    app_ip_proto = fabric_md.lkp.ip_proto;
                    if (fabric_md.bridged.base.encap_presence != EncapPresence.NONE) {
                        uplink_sessions.apply();
                    }
                }
                iface_core: {
                    app_ipv4_addr = fabric_md.lkp.ipv4_src;
                    app_l4_port = fabric_md.lkp.l4_sport;
                    app_ip_proto = fabric_md.lkp.ip_proto;
                    downlink_sessions.apply();
                }
                iface_dbuf: {
                    app_ipv4_addr = fabric_md.lkp.ipv4_src;
                    app_l4_port = fabric_md.lkp.l4_sport;
                    app_ip_proto = fabric_md.lkp.ip_proto;
                    downlink_sessions.apply();
                }
            }

            applications.apply();

            if (sess_hit) {
                if (is_uplink) {
                    uplink_terminations.apply();
                    uplink_recirc_rules.apply();
                } else {
                    downlink_terminations.apply();
                }
            } else {
                // If here it means we haven't set a counter index and we may have
                // not dropped the packet.
                fabric_md.bridged.upf.skip_egress_upf_ctr = true;
            }
            app_meter.execute_meter((bit<32>) app_meter_idx_internal, fabric_md.upf_meter_color);
            if (fabric_md.upf_meter_color != MeterColor_t.RED) {
                // No color-aware meters in v1model, so we should skip session_meter when app meter marked RED.
                session_meter.execute_meter((bit<32>) session_meter_idx_internal, fabric_md.upf_meter_color);
            }
            ig_tunnel_peers.apply();
            if (term_hit) {
                // NOTE We should not update this counter for packets coming
                // **from** dbuf (iface_dbuf), since we already updated it when
                // first sending the same packets **to** dbuf (iface_core).
                // However, putting a condition on the iface type introduces a
                // stage dependency. We trade resource utilization with
                // accounting inaccuracy. Assuming that relatively few packets
                // can be stored at dbuf, and assuming this will be deployed
                // mostly in enterprise settings where we are not billing users,
                // the effects of such inaccuracy should be negligible.
                terminations_counter.count((bit<32>)fabric_md.bridged.upf.upf_ctr_id);
            }
            // Nothing to be done immediately for forwarding or encapsulation.
            // Forwarding is done by other parts of the ingress, and
            // encapsulation is done in the egress
        }
    }
}


//====================================//
//============== Egress ==============//
//====================================//
control UpfEgress(inout ingress_headers_t          hdr,
                   inout fabric_egress_metadata_t  fabric_md) {

    counter(MAX_UPF_COUNTERS, CounterType.packets_and_bytes) terminations_counter;

    //=========================//
    //===== Tunnel Peers ======//
    //=========================//

    action load_tunnel_params(l4_port_t    tunnel_src_port,
                              ipv4_addr_t  tunnel_src_addr,
                              ipv4_addr_t  tunnel_dst_addr) {
        hdr.ipv4.src_addr = tunnel_src_addr;
        hdr.ipv4.dst_addr = tunnel_dst_addr;
        hdr.udp.sport = tunnel_src_port;
    }

    table eg_tunnel_peers {
        key = {
            fabric_md.bridged.upf.tun_peer_id : exact @name("tun_peer_id");
        }
        actions = {
            load_tunnel_params;
            @defaultonly nop;
        }
        const default_action = nop();
        const size = MAX_GTP_TUNNEL_PEERS;
    }

    @hidden
    action _encap_initialize() {
        /** hdr.ipv4 is now outer_ipv4 **/
        hdr.ipv4.version           = 4w4;
        hdr.ipv4.ihl               = 4w5;
        hdr.ipv4.dscp              = 0;
        hdr.ipv4.ecn               = 0;
        // hdr.outer_ipv4.total_len      = update later
        hdr.ipv4.identification    = 0x1513; // From NGIC, TODO: Needs to be dynamic
        hdr.ipv4.flags             = 0;
        hdr.ipv4.frag_offset       = 0;
        hdr.ipv4.ttl               = DEFAULT_IPV4_TTL;
        hdr.ipv4.protocol          = PROTO_UDP;
        // hdr.outer_ipv4.hdr_checksum   = update later
        // hdr.ipv4.src_addr       = update earlier
        // hdr.ipv4.dst_addr       = update earlier
        /** hdr.udp is now outer_udp **/
        // hdr.udp.sport           = update earlier
        hdr.udp.dport              = GTPU_UDP_PORT;
        // hdr.udp.len             = update later
        // hdr.udp.checksum        = update later
        /** outer_gtpu **/
        hdr.gtpu.version           = GTP_V1;
        hdr.gtpu.pt                = GTP_PROTOCOL_TYPE_GTP;
        hdr.gtpu.spare             = 0;
        // hdr.gtpu.ex_flag        = update later
        hdr.gtpu.seq_flag          = 0;
        hdr.gtpu.npdu_flag         = 0;
        hdr.gtpu.msgtype           = GTPU_GPDU;
        // hdr.gtpu.msglen         = update later
        hdr.gtpu.teid              = fabric_md.bridged.upf.teid;
        /** gtpu_options **/
        hdr.gtpu_options.seq_num   = 0;
        hdr.gtpu_options.n_pdu_num = 0;
        hdr.gtpu_options.next_ext  = GTPU_NEXT_EXT_PSC;
        /** gtpu_ext_psc **/
        hdr.gtpu_ext_psc.len       = GTPU_EXT_PSC_LEN;
        hdr.gtpu_ext_psc.type      = GTPU_EXT_PSC_TYPE_DL;
        hdr.gtpu_ext_psc.spare0    = 0;
        hdr.gtpu_ext_psc.ppp       = 0;
        hdr.gtpu_ext_psc.rqi       = 0;
        // hdr.gtpu_ext_psc.qfi    = update later
        hdr.gtpu_ext_psc.next_ext  = GTPU_NEXT_EXT_NONE;
    }

    @hidden
    action _encap_common() {
        // Constant fields initialized in the parser.
        hdr.inner_ipv4.setValid();
        hdr.inner_ipv4 = hdr.ipv4;
        hdr.udp.setValid();
        hdr.gtpu.setValid();
        // For bmv2 the initialization needs to be done after the hdr.*.setValid() is called,
        // otherwise the assignments made in _encap_initialize() have no effect.
        _encap_initialize();
    }

    // Do regular GTP-U encap.
    action gtpu_only() {
        _encap_common();
        hdr.ipv4.total_len = IPV4_HDR_BYTES + UDP_HDR_BYTES + GTPU_HDR_BYTES
                + hdr.inner_ipv4.total_len;
        hdr.udp.len = UDP_HDR_BYTES + GTPU_HDR_BYTES
                + hdr.inner_ipv4.total_len;
        hdr.gtpu.msglen = hdr.inner_ipv4.total_len;
#ifdef WITH_INT
        fabric_md.int_report_md.encap_presence = EncapPresence.GTPU_ONLY;
#endif // WITH_INT
    }

    // Do GTP-U encap with PDU Session Container extension for 5G NG-RAN with
    // configurable QFI.
    action gtpu_with_psc() {
        // Need to set valid before assign any value, in bmv2.
        hdr.gtpu_options.setValid();
        hdr.gtpu_ext_psc.setValid();
        _encap_common();
        hdr.ipv4.total_len = IPV4_HDR_BYTES + UDP_HDR_BYTES + GTPU_HDR_BYTES
                + GTPU_OPTIONS_HDR_BYTES + GTPU_EXT_PSC_HDR_BYTES
                + hdr.inner_ipv4.total_len;
        hdr.udp.len = UDP_HDR_BYTES + GTPU_HDR_BYTES
                + GTPU_OPTIONS_HDR_BYTES + GTPU_EXT_PSC_HDR_BYTES
                + hdr.inner_ipv4.total_len;
        hdr.gtpu.msglen = GTPU_OPTIONS_HDR_BYTES + GTPU_EXT_PSC_HDR_BYTES
                + hdr.inner_ipv4.total_len;
        hdr.gtpu.ex_flag = 1;
        hdr.gtpu_ext_psc.qfi = fabric_md.bridged.upf.qfi;
#ifdef WITH_INT
        fabric_md.int_report_md.encap_presence = EncapPresence.GTPU_WITH_PSC;
#endif // WITH_INT
    }

    // By default, do regular GTP-U encap. Allow the control plane to enable
    // adding PDU Session Container (PSC).
    table gtpu_encap {
        actions = {
            gtpu_only;
            gtpu_with_psc;
        }
        default_action = gtpu_only();
        const size = 1;
    }

    apply {
        if (!fabric_md.bridged.upf.skip_upf) {
            if (fabric_md.bridged.upf.needs_gtpu_encap) {
                if (hdr.udp.isValid()) {
                    hdr.inner_udp.setValid();
                    hdr.inner_udp = hdr.udp;
                    hdr.udp.setInvalid();
                }
                if (hdr.tcp.isValid()) {
                    hdr.inner_tcp.setValid();
                    hdr.inner_tcp = hdr.tcp;
                    hdr.tcp.setInvalid();
                }
                if (hdr.icmp.isValid()) {
                    hdr.inner_icmp.setValid();
                    hdr.inner_icmp = hdr.icmp;
                    hdr.icmp.setInvalid();
                }
                gtpu_encap.apply();
                eg_tunnel_peers.apply();
            }
            if (!fabric_md.bridged.upf.skip_egress_upf_ctr) {
                terminations_counter.count((bit<32>)fabric_md.bridged.upf.upf_ctr_id);
            }
        }
    }
}

#endif // __UPF__
