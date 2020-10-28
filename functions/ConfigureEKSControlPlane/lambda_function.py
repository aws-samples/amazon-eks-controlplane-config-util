import logging
import time
import boto3
from crhelper import CfnResource

logger = logging.getLogger(__name__)
helper = CfnResource(json_logging=True, log_level='INFO')

STATUS_IN_PROGRESS = 'InProgress'
CLUSTER_LOGGING_TYPES = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

try:
    eks_client = boto3.client('eks')
except Exception as init_exception:
    helper.init_failure(init_exception)


@helper.create
@helper.update
def create_update_handler(event, _):
    """
    Handler for create and update actions.
    """

    logger.debug("Event info %s", event)

    props = event['ResourceProperties']
    update_type = props['clusterUpdateType']

    logger.info("Update type %s", update_type)

    update_id = ''

    if update_type and (update_type == 'EndpointAccessUpdate'):
        logging.info('Updating endpoint access of the cluster.')
        update_id = update_api_access_endpoint(
            cluster_name=props['clusterName'],
            private_access=(props['endpointPrivateAccess'] == "True"),
            public_access=(props['endpointPublicAccess'] == "True"),
            public_access_cidrs=props['publicAccessCidrs'])
    elif update_type and (update_type.lower() == 'LoggingUpdate'.lower()):
        logging.info('Updating logging config of the cluster.')
        update_id = update_cluster_logging(
            cluster_name=props['clusterName'],
            cluster_logging_types=props['clusterLoggingTypes'])
    else:
        logging.info('Unsupported update type. No updates will be performed to the cluster.')
        return

    logger.debug("Update ID: %s", update_id)

    if update_id:
        wait_for_update(props['clusterName'], update_id)


def update_api_access_endpoint(cluster_name, private_access, public_access, public_access_cidrs):
    """
    Handle update to API Server access endpoint.
    :param cluster_name: Cluster name
    :param private_access: True/False to turn on/off private access
    :param public_access: True/False to turn on/off public access
    :param public_access_cidrs: List of CIDRs to restrict public access
    """

    logging.info('Private access flag: %s', private_access)
    logging.info('Public access flag: %s', public_access)

    if public_access:
        if (not public_access_cidrs
                or len(public_access_cidrs) < 1
                or not public_access_cidrs[0].strip()):
            # Set public access to 0.0.0.0/0 if no CIDR blocks are specified
            public_access_cidrs = ['0.0.0.0/0']
    else:
        public_access_cidrs = []

    logging.info('Restrict public access to CIDRs: %s', public_access_cidrs)

    # Check if update is needed
    if is_api_access_state_same(cluster_name, private_access, public_access, public_access_cidrs):
        logger.info("API Server access endpoint state is not changing. No update is needed.")
        return None

    response = eks_client.update_cluster_config(
        name=cluster_name,
        resourcesVpcConfig={
            'endpointPublicAccess': public_access,
            'endpointPrivateAccess': private_access,
            'publicAccessCidrs': public_access_cidrs
        }
    )
    return response['update']['id']


def is_api_access_state_same(cluster_name, private_access, public_access, public_access_cidrs):
    """
    Check if the API server access is same.
    :param cluster_name: Cluster name
    :param private_access: True/False to turn on/off private access
    :param public_access: True/False to turn on/off public access
    :param public_access_cidrs: List of CIDRs to restrict public access
    """
    cluster_state = eks_client.describe_cluster(name=cluster_name)
    cluster_vpc_config = cluster_state["cluster"]["resourcesVpcConfig"]
    logger.debug('cluster vpc config: %s', cluster_vpc_config)

    if "publicAccessCidrs" in cluster_vpc_config:
        return (cluster_vpc_config["endpointPrivateAccess"] == private_access) and \
               (cluster_vpc_config["endpointPublicAccess"] == public_access) and \
               (cluster_vpc_config["publicAccessCidrs"] == public_access_cidrs)

    return (cluster_vpc_config["endpointPrivateAccess"] == private_access) and \
           (cluster_vpc_config["endpointPublicAccess"] == public_access)


def update_cluster_logging(cluster_name, cluster_logging_types):
    """
    Update cluster logging config.
    This method accepts list of all logging types that should be enabled.
    NOTE that any logging types that are not listed are disabled.
    :param cluster_name: Cluster name
    :param cluster_logging_types: List of logging types that should be enabled
    """

    # Check if update is needed.
    if is_logging_state_same(cluster_name, cluster_logging_types):
        logger.info("API Server access endpoint state is not changing. No update is needed.")
        return None

    logger.info('clusterLoggingTypes: %s', cluster_logging_types)
    response = eks_client.update_cluster_config(
        name=cluster_name,
        logging={
            'clusterLogging': [
                {
                    'types': cluster_logging_types,
                    'enabled': True
                },
                {
                    'types': list(set(CLUSTER_LOGGING_TYPES).difference(cluster_logging_types)),
                    'enabled': False
                }
            ]
        }
    )
    return response['update']['id']


def is_logging_state_same(cluster_name, cluster_logging_types):
    """
    Check if logging configuration is same.
    :param cluster_name: Cluster name
    :param cluster_logging_types: List of logging types that should be enabled
    """
    cluster_state = eks_client.describe_cluster(name=cluster_name)
    logging_state = cluster_state["cluster"]["logging"]["clusterLogging"]
    logger.info('logging_state : %s', logging_state)

    cluster_log_groups = []
    for log_group in logging_state:
        if log_group["enabled"]:
            cluster_log_groups.extend(log_group["types"])

    logger.info("cluster logs enabled %s", cluster_log_groups)

    return set(cluster_log_groups) == set(cluster_logging_types)


def wait_for_update(cluster_name, update_id):
    """
    Wait for the cluster update to complete.
    :param cluster_name: Cluster name
    :param update_id: Update ID used to check cluster state
    """
    logger.info('Cluster update id  %s ', update_id)
    while True:
        time.sleep(10)
        update_response = eks_client.describe_update(
            name=cluster_name,
            updateId=update_id
        )
        logger.info('Waiting for the cluster update to finish. '
                    'Current update response is %s ', update_response)

        if update_response['update']['status'] != STATUS_IN_PROGRESS:
            break

    logger.info('Cluster update is done')


def lambda_handler(event, context):
    helper(event, context)
