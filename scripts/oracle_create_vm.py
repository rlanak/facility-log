"""Keep trying to create the facility-log VM on Oracle Cloud Always Free
until there is Ampere capacity (São Paulo often answers "Out of host
capacity"). Run with the OCI SDK, kept out of the app's requirements:

    python -m venv ~/.oci/venv && ~/.oci/venv/Scripts/python -m pip install oci
    ~/.oci/venv/Scripts/python scripts/oracle_create_vm.py

Needs ~/.oci/config (API key from the console: Profile -> API keys) and the
SSH public key ~/.ssh/oracle_facility_log.pub. No secret lives in this file.

Stays inside Always Free: VM.Standard.A1.Flex with 2 OCPU / 12 GB (falls
back to 1 / 6 when the bigger one has no room), default boot volume
(~47 GB of the free 200 GB), one VCN with a public subnet. Creates the
network once (reused by name on later runs), then tries the instance every
INTERVAL seconds. Stops on success, printing the public IP, or on any error
that isn't about capacity / rate limiting (so a real problem never loops).
"""

import random
import sys
import time
from datetime import datetime
from pathlib import Path

import oci

NAME = "facility-log"
SHAPE = "VM.Standard.A1.Flex"
SIZES = [(2, 12), (1, 6)]  # (OCPUs, GB): preferred first; total free is 4 / 24
INTERVAL = 75  # seconds between rounds (plus jitter); Oracle throttles faster loops
SSH_KEY = Path.home() / ".ssh" / "oracle_facility_log.pub"
CIDR_VCN, CIDR_SUBNET = "10.0.0.0/16", "10.0.0.0/24"


def log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def ensure_network(net, compartment: str) -> str:
    """VCN + internet gateway + default route + public subnet; returns the subnet id."""
    vcns = [v for v in net.list_vcns(compartment, display_name=f"{NAME}-vcn").data if v.lifecycle_state == "AVAILABLE"]
    if vcns:
        vcn = vcns[0]
    else:
        log("criando VCN")
        vcn = net.create_vcn(
            oci.core.models.CreateVcnDetails(compartment_id=compartment, cidr_blocks=[CIDR_VCN], display_name=f"{NAME}-vcn", dns_label="facilitylog")
        ).data
        vcn = oci.wait_until(net, net.get_vcn(vcn.id), "lifecycle_state", "AVAILABLE").data

    igws = net.list_internet_gateways(compartment, vcn_id=vcn.id).data
    if igws:
        igw = igws[0]
    else:
        log("criando internet gateway")
        igw = net.create_internet_gateway(
            oci.core.models.CreateInternetGatewayDetails(compartment_id=compartment, vcn_id=vcn.id, is_enabled=True, display_name=f"{NAME}-igw")
        ).data
        igw = oci.wait_until(net, net.get_internet_gateway(igw.id), "lifecycle_state", "AVAILABLE").data

    rt = net.get_route_table(vcn.default_route_table_id).data
    if not any(r.network_entity_id == igw.id for r in rt.route_rules):
        log("rota padrão -> internet gateway")
        net.update_route_table(
            rt.id,
            oci.core.models.UpdateRouteTableDetails(
                route_rules=rt.route_rules
                + [oci.core.models.RouteRule(destination="0.0.0.0/0", destination_type="CIDR_BLOCK", network_entity_id=igw.id)]
            ),
        )

    subnets = [s for s in net.list_subnets(compartment, vcn_id=vcn.id).data if s.lifecycle_state == "AVAILABLE"]
    if subnets:
        return subnets[0].id
    log("criando subnet pública")
    subnet = net.create_subnet(
        oci.core.models.CreateSubnetDetails(
            compartment_id=compartment,
            vcn_id=vcn.id,
            cidr_block=CIDR_SUBNET,
            display_name=f"{NAME}-subnet",
            dns_label="public",
            prohibit_public_ip_on_vnic=False,
            route_table_id=vcn.default_route_table_id,
            security_list_ids=[vcn.default_security_list_id],  # default list: only SSH (22) inbound
        )
    ).data
    return oci.wait_until(net, net.get_subnet(subnet.id), "lifecycle_state", "AVAILABLE").data.id


def ubuntu_image(compute, compartment: str) -> str:
    images = compute.list_images(
        compartment,
        operating_system="Canonical Ubuntu",
        operating_system_version="24.04",
        shape=SHAPE,
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    images = [i for i in images if "Minimal" not in i.display_name]
    if not images:
        sys.exit("nenhuma imagem Ubuntu 24.04 para Ampere encontrada")
    log(f"imagem: {images[0].display_name}")
    return images[0].id


def main() -> None:
    cfg = oci.config.from_file()
    compartment = cfg["tenancy"]  # root compartment, like the console form
    identity = oci.identity.IdentityClient(cfg)
    net = oci.core.VirtualNetworkClient(cfg)
    compute = oci.core.ComputeClient(cfg)

    existing = [i for i in compute.list_instances(compartment, display_name=NAME).data if i.lifecycle_state not in ("TERMINATED", "TERMINATING")]
    if existing:
        sys.exit(f"já existe uma instância '{NAME}' ({existing[0].lifecycle_state}); nada a fazer")

    ad = identity.list_availability_domains(compartment).data[0].name
    subnet_id = ensure_network(net, compartment)
    image_id = ubuntu_image(compute, compartment)
    ssh_key = SSH_KEY.read_text().strip()

    attempt = 0
    while True:
        for ocpus, memory in SIZES:
            attempt += 1
            details = oci.core.models.LaunchInstanceDetails(
                compartment_id=compartment,
                availability_domain=ad,
                display_name=NAME,
                shape=SHAPE,
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=memory),
                source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=image_id),
                create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet_id, assign_public_ip=True),
                metadata={"ssh_authorized_keys": ssh_key},
                instance_options=oci.core.models.InstanceOptions(are_legacy_imds_endpoints_disabled=True),
            )
            try:
                instance = compute.launch_instance(details).data
            except oci.exceptions.ServiceError as exc:
                text = f"{exc.code}: {exc.message}"
                if "capacity" in exc.message.lower():
                    log(f"tentativa {attempt} ({ocpus}/{memory}GB): sem capacidade")
                    continue
                if exc.status == 429:
                    log(f"tentativa {attempt}: Oracle pediu calma (429), esperando mais")
                    time.sleep(INTERVAL * 2)
                    continue
                sys.exit(f"erro que não é de capacidade, parando: {text}")
            except (oci.exceptions.RequestException, oci.exceptions.ConnectTimeout, OSError) as exc:
                # Internet dropped (DNS, Wi-Fi): not Oracle's answer, just wait and retry.
                log(f"tentativa {attempt}: sem conexão ({type(exc).__name__}), tentando de novo")
                time.sleep(INTERVAL)
                continue

            log(f"CRIADA com {ocpus} OCPU / {memory} GB, esperando ficar RUNNING")
            instance = oci.wait_until(compute, compute.get_instance(instance.id), "lifecycle_state", "RUNNING", max_wait_seconds=900).data
            vnic_id = compute.list_vnic_attachments(compartment, instance_id=instance.id).data[0].vnic_id
            ip = net.get_vnic(vnic_id).data.public_ip
            log(f"PRONTA: {NAME} rodando, IP público {ip}")
            print(f"PUBLIC_IP={ip}", flush=True)
            return
        time.sleep(INTERVAL + random.randint(0, 30))


if __name__ == "__main__":
    main()
