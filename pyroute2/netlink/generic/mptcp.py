from socket import AF_INET
from socket import AF_INET6
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import genlmsg
from pyroute2.netlink import nla
from pyroute2.netlink.generic import GenericNetlinkSocket

MPTCP_GENL_NAME = 'mptcp_pm'

MPTCP_PM_CMD_UNSPEC = 0
MPTCP_PM_CMD_ADD_ADDR = 1
MPTCP_PM_CMD_DEL_ADDR = 2
MPTCP_PM_CMD_GET_ADDR = 3
MPTCP_PM_CMD_FLUSH_ADDRS = 4
MPTCP_PM_CMD_SET_LIMITS = 5
MPTCP_PM_CMD_GET_LIMITS = 6
MPTCP_PM_CMD_SET_FLAGS = 7


class mptcp_msg(genlmsg):
    nla_map = (('MPTCP_PM_ATTR_UNSPEC', 'none'),
               ('MPTCP_PM_ATTR_ADDR', 'pm_addr'),
               ('MPTCP_PM_ATTR_RCV_ADD_ADDRS', 'uint32'),
               ('MPTCP_PM_ATTR_SUBFLOWS', 'uint32'))

    class pm_addr(nla):
        prefix = 'MPTCP_PM_ADDR_ATTR_'
        nla_map = (('MPTCP_PM_ADDR_ATTR_UNSPEC', 'none'),
                   ('MPTCP_PM_ADDR_ATTR_FAMILY', 'uint16'),
                   ('MPTCP_PM_ADDR_ATTR_ID', 'uint8'),
                   ('MPTCP_PM_ADDR_ATTR_ADDR4', 'ipaddr'),
                   ('MPTCP_PM_ADDR_ATTR_ADDR6', 'ipaddr'),
                   ('MPTCP_PM_ADDR_ATTR_PORT', 'uint16'),
                   ('MPTCP_PM_ADDR_ATTR_FLAGS', 'uint32'),
                   ('MPTCP_PM_ADDR_ATTR_IF_IDX', 'hex'))


class MPTCP(GenericNetlinkSocket):

    def __init__(self):
        super(MPTCP, self).__init__()
        self.bind(MPTCP_GENL_NAME, mptcp_msg)

    def endpoint(self, cmd, **kwarg):
        '''
        Usage::

            mptcp.endpoint('show')
            mptcp.endpoint('add', addr='172.17.20.2')
            mptcp.endpoint('del', id=4)

        Argument `addr` is equal to `addr4` and implies `family=AF_INET`,
        while `addr6` implies `family=AF_INET6`
        '''

        flags_dump = NLM_F_REQUEST | NLM_F_DUMP
        flags_base = NLM_F_REQUEST | NLM_F_ACK
        commands = {'show': (MPTCP_PM_CMD_GET_ADDR, flags_dump),
                    'add': (MPTCP_PM_CMD_ADD_ADDR, flags_base),
                    'del': (MPTCP_PM_CMD_DEL_ADDR, flags_base)}

        (command, flags) = commands.get(cmd, cmd)
        msg = mptcp_msg()
        msg['cmd'] = command
        msg['version'] = 1
        print(msg)

        if cmd in ('add', 'del'):
            addr_info = {'attrs': []}
            if 'addr' in kwarg:
                kwarg['addr4'] = kwarg.pop('addr')
            if 'addr4' in kwarg:
                kwarg['family'] = AF_INET
            elif 'addr6' in kwarg:
                kwarg['family'] = AF_INET6
            for key, value in kwarg.items():
                addr_info['attrs'].append(
                    (mptcp_msg.pm_addr.name2nla(key), value))
            msg['attrs'] = [('MPTCP_PM_ATTR_ADDR', addr_info, 0x8000)]

        return self.nlm_request(
            msg,
            msg_type=self.prid,
            msg_flags=flags)
