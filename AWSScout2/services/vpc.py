# -*- coding: utf-8 -*-

import netaddr

from opinel.utils.aws import get_name
from opinel.utils.globals import manage_dictionary
from opinel.utils.fs import load_data, read_ip_ranges


from AWSScout2.utils import ec2_classic, get_keys
from AWSScout2.configs.regions import RegionalServiceConfig, RegionConfig



########################################
# Globals
########################################

protocols_dict = load_data('protocols.json', 'protocols')



########################################
# VPCRegionConfig
########################################

class VPCRegionConfig(RegionConfig):
    """
    VPC configuration for a single AWS region

    :ivar subnets:                       Dictionary of subnets [name]
    :ivar subnets_count:                 Number of subnets in the region
    """

    def __init__(self):
        self.flow_logs = {}
        self.flow_logs_count = 0
        self.network_acls_count = 0
        self.vpcs = {}
        # Gateways etc... (vpn, internet, nat, ...)


    def parse_flow_log(self, global_params, region, fl):
        """

        :param global_params:
        :param region:
        :param fl:
        :return:
        """
        get_name(fl, fl, 'FlowLogId')
        fl_id = fl.pop('FlowLogId')
        self.flow_logs[fl_id] = fl


    def parse_network_acl(self, global_params, region, network_acl):
        """

        :param global_params:
        :param region:
        :param network_acl:
        :return:
        """
        vpc_id = network_acl['VpcId']
        network_acl['id'] = network_acl.pop('NetworkAclId')
        get_name(network_acl, network_acl, 'id')
        manage_dictionary(network_acl, 'rules', {})
        network_acl['rules']['ingress'] = self.__parse_network_acl_entries(network_acl['Entries'], False)
        network_acl['rules']['egress'] = self.__parse_network_acl_entries(network_acl['Entries'], True)
        network_acl.pop('Entries')
        # Save
        manage_dictionary(self.vpcs, vpc_id, SingleVPCConfig())
        self.vpcs[vpc_id].network_acls[network_acl['id']] = network_acl


    def __parse_network_acl_entries(self, entries, egress):
        """

        :param entries:
        :param egress:
        :return:
        """
        acl_list = []
        for entry in entries:
            if entry['Egress'] == egress:
                acl = {}
                for key in ['CidrBlock', 'RuleAction', 'RuleNumber']:
                    acl[key] = entry[key]
                acl['protocol'] = protocols_dict[entry['Protocol']]
                if 'PortRange' in entry:
                    from_port = entry['PortRange']['From'] if entry['PortRange']['From'] else 1
                    to_port = entry['PortRange']['To'] if entry['PortRange']['To'] else 65535
                    acl['port_range'] = from_port if from_port == to_port else str(from_port) + '-' + str(to_port)
                else:
                    acl['port_range'] = '1-65535'

                acl_list.append(acl)
        return acl_list


    def parse_route_table(self, global_params, region, rt):
        route_table = {}
        vpc_id = rt['VpcId']
        get_name(rt, route_table, 'VpcId') # TODO: change get_name to have src then dst
        get_keys(rt, route_table, ['Routes', 'Associations', 'PropagatingVgws'])
        # Save
        manage_dictionary(self.vpcs, vpc_id, SingleVPCConfig())
        self.vpcs[vpc_id].route_tables[rt['RouteTableId']] = route_table


    def parse_subnet(self, global_params, region, subnet):
        """

        :param global_params:
        :param region:
        :param subnet:
        :return:
        """
        vpc_id = subnet['VpcId']
        manage_dictionary(self.vpcs, vpc_id, SingleVPCConfig())
        subnet_id = subnet['SubnetId']
        get_name(subnet, subnet, 'SubnetId')
        subnet['flow_logs'] = []
        # Save
        manage_dictionary(self.vpcs, vpc_id, SingleVPCConfig())
        self.vpcs[vpc_id].subnets[subnet_id] = subnet


    def parse_vpc(self, global_params, region_name, vpc):
        """

        :param global_params:
        :param region_name:
        :param vpc:
        :return:
        """
        vpc_id = vpc['VpcId']
        # Save
        manage_dictionary(self.vpcs, vpc_id, SingleVPCConfig())
        self.vpcs[vpc_id].name = get_name(vpc, {}, 'VpcId')



########################################
# VPCConfig
########################################

class VPCConfig(RegionalServiceConfig):
    """
    VPC configuration for all AWS regions

    :cvar targets:                      Tuple with all VPC resource names that may be fetched
    :cvar region_config_class:          Class to be used when initiating the service's configuration in a new region
    """
    targets = (
        ('vpcs', 'Vpcs', 'describe_vpcs', False),
        ('flow_logs', 'FlowLogs', 'describe_flow_logs', False),
        ('network_acls', 'NetworkAcls', 'describe_network_acls', False),
        ('route_tables', 'RouteTables', 'describe_route_tables', False),
        ('subnets', 'Subnets', 'describe_subnets', False)
    )
    region_config_class = VPCRegionConfig



########################################
# SingleVPCConfig
########################################

class SingleVPCConfig(object):
    """
    Configuration for a single VPC

    :ivar flow_logs:                    Dictionary of flow logs [id]
    :ivar instances:                    Dictionary of instances [id]
    """

    def __init__(self, name = None):
        self.name = name
        self.network_acls = {}
        self.route_tables = {}
        self.subnets = {}




















########################################
##### VPC analysis functions
########################################



#
# Add a display name for all known CIDRs
#
known_cidrs = {'0.0.0.0/0': 'All'}
def put_cidr_name(aws_config, current_config, path, current_path, resource_id, callback_args):
    if 'cidrs' in current_config:
        cidr_list = []
        for cidr in current_config['cidrs']:
            if type(cidr) == dict:
                cidr = cidr['CIDR']
            if cidr in known_cidrs:
                cidr_name = known_cidrs[cidr]
            else:
                cidr_name = get_cidr_name(cidr, callback_args['ip_ranges'], callback_args['ip_ranges_name_key'])
                known_cidrs[cidr] = cidr_name
            cidr_list.append({'CIDR': cidr, 'CIDRName': cidr_name})
        current_config['cidrs'] = cidr_list

#
# Read display name for CIDRs from ip-ranges files
#
aws_ip_ranges = {} # read_ip_ranges(aws_ip_ranges_filename, False)
def get_cidr_name(cidr, ip_ranges_files, ip_ranges_name_key):
    for filename in ip_ranges_files:
        ip_ranges = read_ip_ranges(filename, local_file = True)
        for ip_range in ip_ranges:
            ip_prefix = netaddr.IPNetwork(ip_range['ip_prefix'])
            cidr = netaddr.IPNetwork(cidr)
            if cidr in ip_prefix:
                return ip_range[ip_ranges_name_key].strip()
    for ip_range in aws_ip_ranges:
        ip_prefix = netaddr.IPNetwork(ip_range['ip_prefix'])
        cidr = netaddr.IPNetwork(cidr)
        if cidr in ip_prefix:
            return 'Unknown CIDR in %s %s' % (ip_range['service'], ip_range['region'])
    return 'Unknown CIDR'

#
# Propagate VPC names in VPC-related services (info only fetched during EC2 calls)
#
def propagate_vpc_names(aws_config, current_config, path, current_path, resource_id, callback_args):
    if resource_id == ec2_classic:
        current_config['name'] = ec2_classic
    else:
        target_path = copy.deepcopy(current_path)
        target_path[1] = 'ec2'
        target_path.append(resource_id)
        target_path.append('Name')
        target_path = '.'.join(target_path)
        current_config['name'] = get_value_at(aws_config, target_path, target_path)
