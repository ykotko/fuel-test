from ipaddr import IPNetwork

from devops.helpers.helpers import _get_file_size
from devops.manager import Manager
from node_roles import NodeRoles, Nodes

from settings import EMPTY_SNAPSHOT, ISO_PATH, INTERFACE_ORDER, POOLS, FORWARDING, DHCP


class Environment(object):
    CAPACITY = 20 * 1024 * 1024 * 1024
    BOOT = ['hd', 'cdrom']
    environment = None
    name = 'fuel'

    def __init__(self, name=name):
        self.manager = Manager()
        self.name = name
        self.environment = self._get_or_create()

    def _get_or_create(self):
        try:
            return self.manager.environment_get(self.name)
        except:
            self.environment = self._create()
            self.environment.define()
            return self.environment

    def nodes(self):
        return Nodes(self.environment, self._node_roles())

    def get_empty_state(self):
        if self.environment.has_snapshot(EMPTY_SNAPSHOT):
            self.environment.revert(EMPTY_SNAPSHOT)
            return True

        return None

    def add_empty_volume(self, node, name, capacity=CAPACITY, device='disk', bus='virtio', format='qcow2'):
        self.manager.node_attach_volume(node=node,
                                        volume=self.manager.volume_create(name=name,
                                                                          capacity=capacity,
                                                                          environment=self.environment,
                                                                          format=format),
                                        device=device,
                                        bus=bus)

    def add_node(self, name, memory, boot=None):
        return self.manager.node_create(name=name,
                                        memory=memory,
                                        environment=self.environment,
                                        boot=boot)

    def create_interfaces(self, node, networks):
        for network in networks:
            self.manager.interface_create(network, node=node)

    def describe_admin_node(self, name, networks, memory=1024, boot=BOOT):
        node = self.add_node(memory=memory, name=name, boot=boot)
        self.create_interfaces(node, networks)
        self.add_empty_volume(node, name + '-system')
        self.add_empty_volume(node, name + '-iso', capacity=_get_file_size(ISO_PATH), format='raw', device='cdrom', bus='ide')

        return node

    def describe_node(self, name, networks, memory=1024):
        node = self.add_node(name, memory)
        self.create_interfaces(node, networks)
        self.add_empty_volume(node, name + '-system')
        #self.add_empty_volume(node, name + '-cinder')
        #self.add_empty_volume(node, name + '-swift')

        return node

    def _node_roles(self):
        return NodeRoles(admin_names=['master'],
                         other_names=['slave-%02d' % x for x in range(1, 2)])

    def _create(self):
        self.environment = self.manager.environment_create(self.name)
        networks = []
        for name in INTERFACE_ORDER:
            ip_networks = [IPNetwork(x) for x in POOLS.get(name)[0].split(',')]
            new_prefix = int(POOLS.get(name)[1])
            pool = self.manager.create_network_pool(networks=ip_networks, prefix=int(new_prefix))
            networks.append(self.manager.network_create(name=name,
                                                        environment=self.environment,
                                                        pool=pool,
                                                        forward=FORWARDING.get(name),
                                                        has_dhcp_server=DHCP.get(name)))

        for name in self._node_roles().admin_names:
            self.describe_admin_node(name, networks)

        for name in self._node_roles().other_names:
            self.describe_node(name, networks, memory=1024)

        return self.environment

    def start(self):
        admin = self.nodes().admin
        admin.disk_devices.get(device='cdrom').volume.upload(ISO_PATH)
        self.environment.start([admin])
        #self._environment.snapshot(EMPTY_SNAPSHOT)

    def get_netmask_by_netname(self, netname):
        return str(IPNetwork(self.environment.network_by_name(netname).ip_network).netmask)

    def get_router_by_netname(self, netname):
        return str(IPNetwork(self.environment.network_by_name(netname).ip_network)[1])

    def internal_virtual_ip(self):
        return self._get_virtual_ip_by_netname('internal')

    def public_virtual_ip(self):
        return self._get_virtual_ip_by_netname('public')

    def _get_virtual_ip_by_netname(self, netname):
        return str(IPNetwork(self.environment.network_by_name(netname).ip_network)[-2])

    # def public_router(self):
    #     return str(IPNetwork(self.get().network_by_name('public').ip_network)[1])
    #
    # def internal_router(self):
    #     return str(IPNetwork(self.get().network_by_name('internal').ip_network)[1])
    #
    # def internal_network(self):
    #     return str(IPNetwork(self.get().network_by_name('internal').ip_network))
    #
    # def public_network(self):
    #     return str(IPNetwork(self.get().network_by_name('public').ip_network))
    #
    # def internal_net_mask(self):
    #     return str(IPNetwork(self.get().network_by_name('internal').ip_network).netmask)
    #
    # def public_net_mask(self):
    #     return str(IPNetwork(self.get().network_by_name('public').ip_network).netmask)


if __name__ == '__main__':
    env = Environment('test')
