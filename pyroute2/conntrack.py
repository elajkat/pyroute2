import socket

from pyroute2.netlink.nfnetlink.nfctsocket import IP_CT_TCP_FLAG_TO_NAME
from pyroute2.netlink.nfnetlink.nfctsocket import IPSBIT_TO_NAME
from pyroute2.netlink.nfnetlink.nfctsocket import TCPF_TO_NAME
from pyroute2.netlink.nfnetlink.nfctsocket import NFCTAttrTuple
from pyroute2.netlink.nfnetlink.nfctsocket import NFCTSocket


class NFCTATcpProtoInfo(object):

    def __init__(self, state, wscale_orig=None, wscale_reply=None,
                 flags_orig=None, flags_reply=None):
        self.state = state
        self.wscale_orig = wscale_orig
        self.wscale_reply = wscale_reply
        self.flags_orig = flags_orig
        self.flags_reply = flags_reply

    def state_name(self):
        return ','.join([name
                         for bit, name in TCPF_TO_NAME.items()
                         if self.state & bit])

    def flags_name(self, flags):
        if flags is None:
            return ''
        s = ''
        for bit, name in IP_CT_TCP_FLAG_TO_NAME.items():
            if flags & bit:
                s += '{},'.format(name)
        return s[:-1]

    @classmethod
    def from_netlink(cls, ndmsg):
        cta_tcp = ndmsg.get_attr('CTA_PROTOINFO_TCP')
        state = cta_tcp.get_attr('CTA_PROTOINFO_TCP_STATE')

        # second argument is the mask returned by kernel but useless for us
        flags_orig, _ = cta_tcp.get_attr('CTA_PROTOINFO_TCP_FLAGS_ORIGINAL')
        flags_reply, _ = cta_tcp.get_attr('CTA_PROTOINFO_TCP_FLAGS_REPLY')
        return cls(state=state, flags_orig=flags_orig, flags_reply=flags_reply)

    def __repr__(self):
        return 'TcpInfo(state={}, orig_flags={}, reply_flags={})'.format(
            self.state_name(), self.flags_name(self.flags_orig),
            self.flags_name(self.flags_reply))


class ConntrackEntry(object):

    def __init__(self, family, tuple_orig, tuple_reply, cta_status,
                 cta_timeout, cta_protoinfo, cta_mark, cta_id, cta_use):
        self.tuple_orig = NFCTAttrTuple.from_netlink(family, tuple_orig)
        self.tuple_reply = NFCTAttrTuple.from_netlink(family, tuple_reply)

        self.status = cta_status
        self.timeout = cta_timeout

        if self.tuple_orig.proto == socket.IPPROTO_TCP:
            self.protoinfo = NFCTATcpProtoInfo.from_netlink(cta_protoinfo)
        else:
            self.protoinfo = None

        self.mark = cta_mark
        self.id = cta_id
        self.use = cta_use

    def status_name(self):
        s = ''
        for bit, name in IPSBIT_TO_NAME.items():
            if self.status & bit:
                s += '{},'.format(name)
        return s[:-1]

    def __repr__(self):
        s = 'Entry(orig={}, reply={}, status={}'.format(
            self.tuple_orig, self.tuple_reply, self.status_name())
        if self.protoinfo is not None:
            s += ', protoinfo={}'.format(self.protoinfo)
        s += ')'
        return s


class Conntrack(NFCTSocket):
    """
    High level conntrack functions
    """

    def stat(self):
        """ Return current statistics per CPU

        Same result than conntrack -S command but a list of dictionaries
        """
        stats = []

        for msg in super(Conntrack, self).stat():
            stats.append({'cpu': msg['res_id']})
            stats[-1].update((k[10:].lower(), v) for k, v in msg['attrs']
                             if k.startswith('CTA_STATS_'))

        return stats

    def count(self):
        """ Return current number of conntrack entries

        Same result than /proc/sys/net/netfilter/nf_conntrack_count file
        or conntrack -C command
        """
        ndmsg = super(Conntrack, self).count()
        return ndmsg[0].get_attr('CTA_STATS_GLOBAL_ENTRIES')

    def conntrack_max_size(self):
        """
        Return the max size of connection tracking table
        /proc/sys/net/netfilter/nf_conntrack_max
        """
        ndmsg = super(Conntrack, self).conntrack_max_size()
        return ndmsg[0].get_attr('CTA_STATS_GLOBAL_MAX_ENTRIES')

    def delete(self, entry):
        if isinstance(entry, ConntrackEntry):
            tuple_orig = entry.tuple_orig
        elif isinstance(entry, NFCTAttrTuple):
            tuple_orig = entry
        else:
            raise NotImplementedError()
        self.entry('del', tuple_orig=tuple_orig)

    def dump_entries(self, mark=None, mark_mask=0xffffffff, tuple_orig=None,
                     tuple_reply=None):
        """
        Dump all entries from conntrack table with filters

        Filters can be only part of a conntrack tuple

        :param NFCTAttrTuple tuple_orig: filter on original tuple
        :param NFCTAttrTuple tuple_reply: filter on reply tuple
        """
        for ndmsg in super(Conntrack, self).dump(mark=mark, mark_mask=mark_mask):
            if tuple_orig is not None and not tuple_orig.nla_eq(
                    ndmsg['nfgen_family'], ndmsg.get_attr('CTA_TUPLE_ORIG')):
                continue

            if tuple_reply is not None and not tuple_reply.nla_eq(
                    ndmsg['nfgen_family'], ndmsg.get_attr('CTA_TUPLE_REPLY')):
                continue

            yield ConntrackEntry(
                ndmsg['nfgen_family'],
                ndmsg.get_attr('CTA_TUPLE_ORIG'),
                ndmsg.get_attr('CTA_TUPLE_REPLY'),
                ndmsg.get_attr('CTA_STATUS'),
                ndmsg.get_attr('CTA_TIMEOUT'),
                ndmsg.get_attr('CTA_PROTOINFO'),
                ndmsg.get_attr('CTA_MARK'),
                ndmsg.get_attr('CTA_ID'),
                ndmsg.get_attr('CTA_USE'),
            )
