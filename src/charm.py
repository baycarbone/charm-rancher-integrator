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
from ops.pebble import APIError, PathError
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)

class RancherIntegratorCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.register_action, self._on_register_action)
        self.framework.observe(self.on.unregister_action, self._on_unregister_action)
        self.framework.observe(self.on.cluster_control_relation_changed,
                               self._on_cluster_control_relation_changed)
        self._stored.set_default(manifest=None, cluster_name=None, registered=False)
        self.kubernetes = Kubernetes('cattle-system')

    def _on_config_changed(self, event):
        """Check if the Rancher API is reachable with new config.

        If the API connection details are changed,
        make sure the API is still reachable.

        """

        command = 'verify'
        outcome = self._rancher_integrator_layer(command)

        if outcome['status']:
            # All is well, set an ActiveStatus
            if self._stored.registered:
                self.unit.status = ActiveStatus()
            else:
                self.unit.status = ActiveStatus('Cluster is not registered.')
        else:
            message = outcome['reason'].split('Err -')
            # Block and inform user api connection details need to be sorted out
            self.unit.status = BlockedStatus(message[0])

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

        if not self._stored.registered:
            if not self._stored.cluster_name and 'name' in event.params:
                self._stored.cluster_name = event.params['name']
            container = self.unit.get_container('rancher-integrator')
            command = 'register'
            outcome = self._rancher_integrator_layer(command)

            if outcome['status']:
                event.log('Cluster successfuly registered, trying to fetch the import manifest...')
                found_manifest = False
                count = 0
                while not found_manifest and count < 5:
                    try:
                        import_manifest_contents = container.list_files('/usr/src/app/import_manifest/', pattern='*.yaml')
                    except APIError as err:
                        event.fail('Unable to retrieve manifest file from rancher-integrator. Error: {}'.format(err))
                        command = 'unregister'
                        self._rancher_integrator_layer(command)
                        return
                    if len(import_manifest_contents) == 1:
                        try:
                            #import_manifest = container.pull('/blabla/i.yaml').read()
                            import_manifest = container.pull(import_manifest_contents[0].path).read()
                            self._stored.cluster_name = import_manifest_contents[0].name.split('.yaml')[0]
                        except PathError as err:
                            event.fail('Unable to retrieve manifest file from rancher-integrator. Error: {}'.format(err))
                            command = 'unregister'
                            self._rancher_integrator_layer(command)
                            return
                        found_manifest = True
                    else:
                        count += 1
                        time.sleep(1)

                if found_manifest:
                    event.log('Successully fetched the import manifest, now applying it...')
                    if import_manifest != self._stored.manifest:
                        self._stored.manifest = import_manifest
                    try:
                        self.kubernetes.apply(self._stored.manifest)
                    except ApiException as err:
                        if err.status == 403:
                            event.fail(
                                'Insufficient permissions to apply import manifest. Try: `juju trust {} --scope=cluster`'.format(
                                self.app.name
                                )
                            )
                        else:
                            event.fail('Unable to apply import manifest. ApiException: {}'.format(err))
                        command = 'unregister'
                        self._rancher_integrator_layer(command)
                        return

                    event.log('Successully applied import manifest.')
                    event.set_results({
                        'result': 'Cluster registered.',
                        'name': self._stored.cluster_name
                        })
                    self._stored.registered = True
                    self.unit.status = ActiveStatus('Registered cluster: {}'.format(self._stored.cluster_name))
                else:
                    event.fail('Unable to retrieve manifest file from rancher-integrator. Max tries exceeded.')
                    command = 'unregister'
                    self._rancher_integrator_layer(command)
                    return
            else:
                message = outcome['reason'].split('Err -')
                event.fail('Unable to register cluster. Error: {}'.format(message))
                return

        else:
            event.set_results({
                'result': 'Cluster already registered. Please unregister {} before trying again.'.format(self._stored.cluster_name),
                'name': self._stored.cluster_name
                })

    def _on_unregister_action(self, event):
        """Register the Kubernetes cluster in a Rancher platform.

        Using the configured API connection details, register
        the Kubernetes cluster into the specified Rancher platform.

        """

        command = 'unregister'
        outcome = self._rancher_integrator_layer(command)

        if outcome['status']:
            event.log('Successully unregistered cluster from rancher platform.')
            if self._stored.manifest is not None:
                self.kubernetes.delete(self._stored.manifest)
                event.log('Successully removed import manifest.')
                self._stored.manifest = None
            event.set_results({
                'result': 'Unregistered cluster successfully',
                'name': self._stored.cluster_name
                })
            self._stored.cluster_name = None
            self._stored.registered = False
            # All is well, set an ActiveStatus
            self.unit.status = ActiveStatus('Cluster is not registered.')
        else:
            message = outcome['reason'].split('Err -')
            # Block and inform user api connection details need to be sorted out
            self.unit.status = BlockedStatus(message[0])
            event.fail(message='Unable to unregister cluster. Error: {}'.format(message[0]))

    def _rancher_integrator_layer(self, command):
        """Returns a Pebble configration layer for rancher-integrator"""

        # Get the rancher-integrator container so we can configure/manipulate it
        container = self.unit.get_container('rancher-integrator')

        # Set env dictionary based on config options
        env = {
            'RANCHER_INTEGRATOR_WAIT': 'True',
            'RANCHER_INTEGRATOR_CERT_CHECK': self.config['cert-verify']
            }

        if 'url' in self.config:
            env['RANCHER_INTEGRATOR_URL'] = self.config['url']
        if 'bearer-token' in self.config:
            split_token = self.config['bearer-token'].split(":")
            if len(split_token) == 2:
                env['RANCHER_INTEGRATOR_USERNAME'] = split_token[0]
                env['RANCHER_INTEGRATOR_PASSWORD'] = split_token[1]
        if self._stored.cluster_name:
            env['RANCHER_INTEGRATOR_CLUSTER_NAME'] = self._stored.cluster_name
        # Create a new config layer
        layer = {
            "summary": "rancher-integrator layer",
            "description": "pebble config layer for rancher-integrator",
            "services": {
                "rancher-integrator": {
                    "override": "replace",
                    "summary": "rancher-integrator",
                    "command": 'python3 ./rancher-integrator.py ' + command,
                    "startup": "enabled",
                    "environment": env,
                }
            },
        }

        try:
            # Get the current config
            services = container.get_plan().to_dict().get("services", {})
        except ConnectionError:
            # Since this is a config-changed handler and that hook can execute
            # before pebble is ready, we may get a connection error here. Let's
            # defer the event, meaning it will be retried the next time any
            # hook is executed. We don't have an explicit handler for
            # `self.on.gosherve_pebble_ready` but this method will be rerun
            # when that condition is met (because of `event.defer()`), and so
            # the `get_container` call will succeed and we'll continue to the
            # subsequent steps.
            event.defer()
            return {'status': True}
        # Check if there are any changes to services
        if services != layer["services"]:
            # Changes were made, add the new layer
            container.add_layer('rancher-integrator', layer, combine=True)
            logger.info("Added updated layer 'rancher-integrator' to Pebble plan")
            # Stop the service if it is already running
            if container.get_service('rancher-integrator').is_running():
                container.stop('rancher-integrator')
            # Restart it and report a new status to Juju
            container.start('rancher-integrator')
            logger.info("Restarted rancher-integrator service")

            error_log = container.pull('/usr/src/app/error.log').read()

            if error_log:
                return {'status': False, 'reason': error_log}

        return {'status': True}

if __name__ == "__main__":
    main(RancherIntegratorCharm)