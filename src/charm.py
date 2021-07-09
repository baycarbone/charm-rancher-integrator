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
        self.framework.observe(self.on.delete_action, self._on_delete_action)
        self.framework.observe(self.on.cluster_control_relation_changed, self._on_cluster_control_relation_changed)
        self._stored.set_default(url=self.config["url"], bearer_token=self.config["bearer-token"], cert_verify=self.config["cert-verify"], manifest=None)
        self.kubernetes = Kubernetes('cattle-system')

    def _on_rancher_integrator_pebble_ready(self, event):
        """Define and start a workload using the Pebble API.

        TEMPLATE-TODO: change this example to suit your needs.
        You'll need to specify the right entrypoint and environment
        configuration for your specific workload. Tip: you can see the
        standard entrypoint of an existing container using docker inspect

        Learn more about Pebble layers at https://github.com/canonical/pebble
        """

        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
        # Define an initial Pebble layer configuration

        pebble_layer = {
            "summary": "rancher integrator layer",
            "description": "pebble config layer for rancher integrator",
            "services": {
                "rancher-integrator": {
                    "override": "replace",
                    "summary": "rancher integrator",
                    "command": "sleep 30s",
                    "startup": "enabled",
                    "environment": {
                        "TOKEN": self.model.name,
                    },
                }
            },
        }
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("rancher-integrator", pebble_layer, combine=True)
        # Autostart any services that were defined with startup: enabled
        container.autostart()
        # Learn more about statuses in the SDK docs:
        # https://juju.is/docs/sdk/constructs#heading--statuses
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, _):
        """Just an example to show how to deal with changed configuration.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle config, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the config.py file.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        # current = self.config["thing"]
        # if current not in self._stored.things:
        #     logger.debug("found a new thing: %r", current)
        #     self._stored.things.append(current)
        pass


    def _on_cluster_control_relation_changed(self, event):
        """Just an example to show how to receive actions.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle actions, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the actions.py file.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """
        pass

    def _on_register_action(self, event):
        """Just an example to show how to receive actions.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle actions, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the actions.py file.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """

        container = self.unit.get_container("rancher-integrator")

        cmd = "python ./rancher-integrator.py -i -d " + self.config["url"] + " " + self.config["bearer-token"].split(":")[0] + " " + self.config["bearer-token"].split(":")[1] + " register -n" + self.config["cluster-name"]

        pebble_layer = {
            "summary": "rancher integrator layer",
            "description": "pebble config layer for rancher integrator",
            "services": {
                "rancher-integrator": {
                    "override": "replace",
                    "summary": "rancher integrator",
                    "command": cmd,
                    "startup": "enabled",
                    "environment": {
                        "TOKEN": self.model.name,
                    },
                }
            },
        }

        # Add intial Pebble config layer using the Pebble API
        container.add_layer("rancher-integrator", pebble_layer, combine=True)
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

    def _on_delete_action(self, event):
        """Just an example to show how to receive actions.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle actions, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the actions.py file.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """
        container = self.unit.get_container("rancher-integrator")

        cmd = "python ./rancher-integrator.py -i -d " + self.config["url"] + " " + self.config["bearer-token"].split(":")[0] + " " + self.config["bearer-token"].split(":")[1] + " delete " + self.config["cluster-name"]

        pebble_layer = {
            "summary": "rancher integrator layer",
            "description": "pebble config layer for rancher integrator",
            "services": {
                "rancher-integrator": {
                    "override": "replace",
                    "summary": "rancher integrator",
                    "command": cmd,
                    "startup": "enabled",
                    "environment": {
                        "TOKEN": self.model.name,
                    },
                }
            },
        }

        # Add intial Pebble config layer using the Pebble API
        container.add_layer("rancher-integrator", pebble_layer, combine=True)
        logging.info("Added updated layer 'rancher-integrator' to Pebble plan to run register command")

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

if __name__ == "__main__":
    main(RancherIntegratorCharm)