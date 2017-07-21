"""
Helper methods for generating k8s API objects.
"""
import json
from urllib.parse import urlparse
import escapism
import string

from kubernetes.client.models import \
    V1Pod, V1PodSpec, V1PodSecurityContext, \
    V1ObjectMeta, \
    V1LocalObjectReference, \
    V1Container, V1ContainerPort, V1EnvVar, V1ResourceRequirements, \
    V1PersistentVolumeClaim, V1PersistentVolumeClaimSpec, \
    V1Endpoints, V1EndpointSubset, V1EndpointAddress, V1EndpointPort, \
    V1Service, V1ServiceSpec, V1ServicePort, \
    V1beta1Ingress, V1beta1IngressSpec, V1beta1IngressRule, \
    V1beta1HTTPIngressRuleValue, V1beta1HTTPIngressPath, \
    V1beta1IngressBackend

def make_pod(
    name,
    image_spec,
    image_pull_policy,
    image_pull_secret,
    port,
    cmd,
    node_selector,
    run_as_uid,
    fs_gid,
    env,
    working_dir,
    volumes,
    volume_mounts,
    labels,
    cpu_limit,
    cpu_guarantee,
    mem_limit,
    mem_guarantee,
    lifecycle_hooks,
    init_containers,
):
    """
    Make a k8s pod specification for running a user notebook.

    Parameters:
      - name:
        Name of pod. Must be unique within the namespace the object is
        going to be created in. Must be a valid DNS label.
      - image_spec:
        Image specification - usually a image name and tag in the form
        of image_name:tag. Same thing you would use with docker commandline
        arguments
      - image_pull_policy:
        Image pull policy - one of 'Always', 'IfNotPresent' or 'Never'. Decides
        when kubernetes will check for a newer version of image and pull it when
        running a pod.
      - image_pull_secret:
        Image pull secret - Default is None -- set to your secret name to pull
        from private docker registry.
      - port:
        Port the notebook server is going to be listening on
      - cmd:
        The command used to execute the singleuser server.
      - node_selector:
        Dictionary Selector to match nodes where to launch the Pods
      - run_as_uid:
        The UID used to run single-user pods. The default is to run as the user
        specified in the Dockerfile, if this is set to None.
      - fs_gid
        The gid that will own any fresh volumes mounted into this pod, if using
        volume types that support this (such as GCE). This should be a group that
        the uid the process is running as should be a member of, so that it can
        read / write to the volumes mounted.
      - env:
        Dictionary of environment variables.
      - volumes:
        List of dictionaries containing the volumes of various types this pod
        will be using. See k8s documentation about volumes on how to specify
        these
      - volume_mounts:
        List of dictionaries mapping paths in the container and the volume(
        specified in volumes) that should be mounted on them. See the k8s
        documentaiton for more details
      - working_dir:
        String specifying the working directory for the notebook container
      - labels:
        Labels to add to the spawned pod.
      - cpu_limit:
        Float specifying the max number of CPU cores the user's pod is
        allowed to use.
      - cpu_guarentee:
        Float specifying the max number of CPU cores the user's pod is
        guaranteed to have access to, by the scheduler.
      - mem_limit:
        String specifying the max amount of RAM the user's pod is allowed
        to use. String instead of float/int since common suffixes are allowed
      - mem_guarantee:
        String specifying the max amount of RAM the user's pod is guaranteed
        to have access to. String ins loat/int since common suffixes
        are allowed
      - lifecycle_hooks:
        Dictionary of lifecycle hooks
      - init_containers:
        List of initialization containers belonging to the pod.
    """

    pod = V1Pod()
    pod.kind = "Pod"
    pod.api_version = "v1"

    pod.metadata = V1ObjectMeta()
    pod.metadata.name = name
    pod.metadata.labels = labels.copy()

    pod.spec = V1PodSpec()

    security_context = V1PodSecurityContext()
    if fs_gid is not None:
        security_context.fs_group = int(fs_gid)
    if run_as_uid is not None:
        security_context.run_as_user = int(run_as_uid)
    pod.spec.security_context = security_context

    if image_pull_secret is not None:
        pod.spec.image_pull_secrets = []
        image_secret = V1LocalObjectReference()
        image_secret.name = image_pull_secret
        pod.spec.image_pull_secrets.append(image_secret)

    if node_selector:
        pod.spec.node_selector = node_selector

    pod.spec.containers = []
    notebook_container = V1Container()
    notebook_container.name = "notebook"
    notebook_container.image = image_spec
    notebook_container.working_dir = working_dir
    notebook_container.ports = []
    port_ = V1ContainerPort()
    port_.name = "notebook-port"
    port_.container_port = port
    notebook_container.ports.append(port_)
    notebook_container.env = [V1EnvVar(k, v) for k, v in env.items()]
    notebook_container.args = cmd
    notebook_container.image_pull_policy = image_pull_policy
    notebook_container.lifecycle = lifecycle_hooks
    notebook_container.resources = V1ResourceRequirements()

    notebook_container.resources.requests = {}

    if cpu_guarantee:
        notebook_container.resources.requests['cpu'] = cpu_guarantee
    if mem_guarantee:
        notebook_container.resources.requests['memory'] = mem_guarantee

    notebook_container.resources.limits = {}
    if cpu_limit:
        notebook_container.resources.limits['cpu'] = cpu_limit
    if mem_limit:
        notebook_container.resources.limits['memory'] = mem_limit
    notebook_container.volume_mounts = volume_mounts
    pod.spec.containers.append(notebook_container)

    pod.spec.init_containers = init_containers
    pod.spec.volumes = volumes
    return pod


def make_pvc(
    name,
    storage_class,
    access_modes,
    storage,
    labels
    ):
    """
    Make a k8s pvc specification for running a user notebook.

    Parameters:
      - name:
        Name of persistent volume claim. Must be unique within the namespace the object is
        going to be created in. Must be a valid DNS label.
      - storage_class
      String of the name of the k8s Storage Class to use.
      - access_modes:
      A list of specifying what access mode the pod should have towards the pvc
      - storage
      The ammount of storage needed for the pvc
    """
    pvc = V1PersistentVolumeClaim()
    pvc.kind = "PersistentVolumeClaim"
    pvc.api_version = "v1"
    pvc.metadata = V1ObjectMeta()
    pvc.metadata.name = name
    pvc.metadata.annotations = {}
    if storage_class:
        pvc.metadata.annotations.update({"volume.beta.kubernetes.io/storage-class": storage_class})
    pvc.metadata.labels = {}
    pvc.metadata.labels.update(labels)
    pvc.spec = V1PersistentVolumeClaimSpec()
    pvc.spec.access_modes = access_modes
    pvc.spec.resources = V1ResourceRequirements()
    pvc.spec.resources.requests = {"storage": storage}

    return pvc


def make_ingress(
        name,
        routespec,
        target,
        data
):
    """
    Returns an ingress, service, endpoint object that'll work for this service
    """
    meta = V1ObjectMeta(
        name=name,
        annotations={
            'hub.jupyter.org/proxy-data': json.dumps(data),
            'hub.jupyter.org/proxy-routespec': routespec,
            'hub.jupyter.org/proxy-target': target
        },
        labels={
            'heritage': 'jupyterhub',
            'component': 'singleuser-server',
            'hub.jupyter.org/proxy-route': 'true'
        }
    )

    if routespec.startswith('/'):
        host = None
        path = routespec
    else:
        host, path = routespec.split('/', 1)

    target_parts = urlparse(target)

    target_ip = target_parts.hostname
    target_port = target_parts.port

    # Make endpoint object
    endpoint = V1Endpoints(
        kind='Endpoints',
        metadata=meta,
        subsets=[
            V1EndpointSubset(
                addresses=[V1EndpointAddress(ip=target_ip)],
                ports=[V1EndpointPort(port=target_port)]
            )
        ]
    )

    # Make service object
    service = V1Service(
        kind='Service',
        metadata=meta,
        spec=V1ServiceSpec(
            ports=[V1ServicePort(port=target_port, target_port=target_port)]
        )
    )

    # Make Ingress object
    ingress = V1beta1Ingress(
        kind='Ingress',
        metadata=meta,
        spec=V1beta1IngressSpec(
            rules=[V1beta1IngressRule(
                host=host,
                http=V1beta1HTTPIngressRuleValue(
                    paths=[
                        V1beta1HTTPIngressPath(
                            path=path,
                            backend=V1beta1IngressBackend(
                                service_name=name,
                                service_port=target_port
                            )
                        )
                    ]
                )
            )]
        )
    )

    return endpoint, service, ingress
