"""AWS SRE tools for CloudSentry: CloudWatch alarms, telemetry, and guarded remediation actions.

Safe diagnostic tools run freely; high-impact remediation tools (restart, scale, rollback, isolate)
are intercepted and guarded by Strands Decider 2B.
"""

from __future__ import annotations

from strands import tool

CLUSTERS = {
    "prod-ecommerce": {
        "services": {
            "checkout-api": {"revision": "v2.14.0", "healthy": False, "cpu": 94.2, "error_5xx": 8.7, "tasks": 4},
            "payment-gateway": {"revision": "v1.9.3", "healthy": True, "cpu": 32.1, "error_5xx": 0.05, "tasks": 6},
            "inventory-svc": {"revision": "v3.1.2", "healthy": True, "cpu": 28.5, "error_5xx": 0.0, "tasks": 3},
        },
        "asgs": {
            "asg-prod-checkout": {"current": 4, "min": 2, "max": 12, "desired": 4},
            "asg-prod-payment": {"current": 6, "min": 3, "max": 16, "desired": 6},
        },
    }
}

ACTIVE_ALARMS = [
    {
        "alarm_name": "checkout-api-HighCPU-High5XX",
        "service": "checkout-api",
        "cluster": "prod-ecommerce",
        "state": "ALARM",
        "metric": "CPUUtilization > 85% AND HTTPCode_Target_5XX_Count > 5%",
        "reason": "Threshold breached: checkout-api CPU at 94.2%, 5XX error rate 8.7% after release v2.14.0",
        "last_updated": "2 minutes ago",
    },
    {
        "alarm_name": "payment-gateway-LatencySpike",
        "service": "payment-gateway",
        "cluster": "prod-ecommerce",
        "state": "OK",
        "metric": "TargetResponseTime < 250ms",
        "reason": "Normal operational bounds",
        "last_updated": "15 minutes ago",
    },
]

ACTIONS_AUDIT_LOG: list[dict] = []


@tool
def query_cloudwatch_alarms(service_name: str = "") -> dict:
    """Query active AWS CloudWatch alarms, optionally filtered by service name."""
    svc = service_name.strip().lower()
    if svc:
        matched = [a for a in ACTIVE_ALARMS if svc in a["service"].lower()]
        return {"count": len(matched), "alarms": matched}
    return {"count": len(ACTIVE_ALARMS), "alarms": ACTIVE_ALARMS}


@tool
def get_service_telemetry(service_name: str, metric_name: str = "CPUUtilization") -> dict:
    """Fetch recent CloudWatch metric datapoints for a service (e.g. CPUUtilization, HTTPCode_5XX)."""
    svc = service_name.strip().lower()
    cluster = CLUSTERS["prod-ecommerce"]["services"].get(svc)
    if not cluster:
        return {"error": f"Service '{service_name}' not found in CloudWatch metrics."}
    return {
        "service": service_name,
        "metric": metric_name,
        "current_value": cluster.get("cpu" if "cpu" in metric_name.lower() else "error_5xx"),
        "healthy": cluster.get("healthy"),
        "revision": cluster.get("revision"),
        "timestamp": "2026-10-23T22:30:00Z",
    }


@tool
def restart_service(cluster: str, service_name: str) -> dict:
    """Restart an ECS/EKS service tasks gracefully to recover from deadlock or memory leak (guarded)."""
    svc_dict = CLUSTERS.get(cluster, {}).get("services", {})
    if service_name not in svc_dict:
        return {"error": f"Service '{service_name}' not found in cluster '{cluster}'."}
    ACTIONS_AUDIT_LOG.append({"action": "restart_service", "cluster": cluster, "service": service_name})
    svc_dict[service_name]["healthy"] = True
    svc_dict[service_name]["cpu"] = 35.0
    return {"status": "SUCCESS", "message": f"Service '{service_name}' restarted on '{cluster}'. New deployment rolling out."}


@tool
def scale_asg(asg_name: str, desired_capacity: int) -> dict:
    """Scale an AWS Auto Scaling Group to a new desired capacity to handle traffic spikes (guarded)."""
    asgs = CLUSTERS["prod-ecommerce"]["asgs"]
    if asg_name not in asgs:
        return {"error": f"ASG '{asg_name}' not found."}
    if desired_capacity > asgs[asg_name]["max"]:
        return {"error": f"Desired capacity {desired_capacity} exceeds ASG maximum {asgs[asg_name]['max']}."}
    asgs[asg_name]["desired"] = desired_capacity
    ACTIONS_AUDIT_LOG.append({"action": "scale_asg", "asg": asg_name, "desired_capacity": desired_capacity})
    return {"status": "SUCCESS", "asg": asg_name, "new_desired_capacity": desired_capacity}


@tool
def rollback_deployment(cluster: str, service_name: str, target_revision: str) -> dict:
    """Roll back an ECS/EKS service deployment to a verified previous stable task definition (guarded)."""
    svc_dict = CLUSTERS.get(cluster, {}).get("services", {})
    if service_name not in svc_dict:
        return {"error": f"Service '{service_name}' not found in cluster '{cluster}'."}
    ACTIONS_AUDIT_LOG.append({"action": "rollback_deployment", "cluster": cluster, "service": service_name, "target_revision": target_revision})
    svc_dict[service_name]["revision"] = target_revision
    svc_dict[service_name]["healthy"] = True
    svc_dict[service_name]["error_5xx"] = 0.02
    return {"status": "SUCCESS", "message": f"Rolled back '{service_name}' in cluster '{cluster}' to stable revision '{target_revision}'."}


@tool
def isolate_instance(instance_id: str) -> dict:
    """Quarantine a compromised or malfunctioning EC2 instance by attaching an isolation security group (guarded)."""
    ACTIONS_AUDIT_LOG.append({"action": "isolate_instance", "instance_id": instance_id})
    return {"status": "SUCCESS", "message": f"Instance '{instance_id}' isolated. Ingress/egress restricted to forensic VPC."}


TOOLS = [query_cloudwatch_alarms, get_service_telemetry, restart_service, scale_asg, rollback_deployment, isolate_instance]
