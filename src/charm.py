#!/usr/bin/env python3
# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
import time

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus
from kubernetes_wrapper import Kubernetes

logger = logging.getLogger(__name__)


class RancherIntegratorCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.rancher_integrator_pebble_ready, self._on_rancher_integrator_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.register_action, self._on_register_action)
        self.framework.observe(self.on.unregister_action, self._on_unregister_action)
        self.framework.observe(self.on.cluster_control_relation_changed, self._on_cluster_control_relation_changed)
        self._stored.set_default(url=self.config["url"], bearer_token=self.config["bearer-token"], cert_verify=self.config["cert-verify"], manifest=None)
        self.kubernetes = Kubernetes('cattle-system')
        self.cmd = "sleep 30s"

    def _on_rancher_integrator_pebble_ready(self, event):
        """Define and start the rancher-integrator workload using the Pebble API.

        As the rancher-integrator is essentially a one and done cli tool,
        we start the container with a simple sleep command.

        """

        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload

        # Add intial Pebble config layer using the Pebble API
        container.add_layer("rancher-integrator", self._rancher_integrator_layer(), combine=True)
        # Autostart any services that were defined with startup: enabled
        container.autostart()
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, _):
        """Check if the Rancher API is reachable with new config.

        If the API connection details are changed,
        make sure the API is still reachable.

        """
        # Implement api reachability check
        pass

    def _on_cluster_control_relation_changed(self, event):
        """Retrieve API connection details when relating to a charmed Rancher deployment

        If this charm is related to a charmed Rancher platform through
        cross model relation, retrieve the API connection details from
        the relation and save them in the stored state.

        """
        # Implement relation handling
        pass

    def _on_register_action(self, event):
        """Register the Kubernetes cluster in a Rancher platform.

        Using the configured API connection details, register
        the Kubernetes cluster into the specified Rancher platform.

        """

        container = self.unit.get_container("rancher-integrator")

        self.cmd = "python ./rancher-integrator.py -i -w " + self.config["url"] + " " + self.config["bearer-token"].split(":")[0] + " " + self.config["bearer-token"].split(":")[1] + " register -n" + self.config["cluster-name"]

        # Add intial Pebble config layer using the Pebble API
        container.add_layer("rancher-integrator", self._rancher_integrator_layer(), combine=True)
        logging.info("Added updated layer 'rancher-integrator' to Pebble plan to run register command")

        # Stop the service if it is already running
        if container.get_service("rancher-integrator").is_running():
            logging.info("Stopping rancher-integrator service")
            container.stop("rancher-integrator")
            # Restart it and report a new status to Juju
            container.start("rancher-integrator")
            logging.info("Restarted rancher-integrator service")

        time.sleep(7)
        import_manifest = container.pull('/usr/src/app/import_manifest/import_' + self.config["cluster-name"] + '.yaml').read()
        logging.info("Manifest: %s", import_manifest)
        if import_manifest != self._stored.manifest:
            self._stored.manifest = import_manifest
        self.kubernetes.apply(self._stored.manifest)
        # All is well, set an ActiveStatus
        self.unit.status = ActiveStatus()

    def _on_unregister_action(self, event):
        """Register the Kubernetes cluster in a Rancher platform.

        Using the configured API connection details, register
        the Kubernetes cluster into the specified Rancher platform.

        """
        container = self.unit.get_container("rancher-integrator")

        self.cmd = "python ./rancher-integrator.py -i -w " + self.config["url"] + " " + self.config["bearer-token"].split(":")[0] + " " + self.config["bearer-token"].split(":")[1] + " unregister " + self.config["cluster-name"]

        # Add intial Pebble config layer using the Pebble API
        container.add_layer("rancher-integrator", self._rancher_integrator_layer(), combine=True)
        logging.info("Added updated layer 'rancher-integrator' to Pebble plan to run unregister command")

        # Stop the service if it is already running
        if container.get_service("rancher-integrator").is_running():
            logging.info("Stopping rancher-integrator service")
            container.stop("rancher-integrator")
            # Restart it and report a new status to Juju
            container.start("rancher-integrator")
            logging.info("Restarted rancher-integrator service")

        if self._stored.manifest is not None:
            self.kubernetes.delete(self._stored.manifest)
        # All is well, set an ActiveStatus
        self.unit.status = ActiveStatus()

    def _rancher_integrator_layer(self):
        """Returns a Pebble configration layer for rancher-integrator"""
        return {
            "summary": "rancher-integrator layer",
            "description": "pebble config layer for rancher-integrator",
            "services": {
                "rancher-integrator": {
                    "override": "replace",
                    "summary": "rancher-integrator",
                    "command": self.cmd,
                    "startup": "enabled",
                    "environment": {
                        "TOKEN": self.model.name,
                    },
                }
            },
        }

if __name__ == "__main__":
    main(RancherIntegratorCharm)