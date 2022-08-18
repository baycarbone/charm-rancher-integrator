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

        verify_layer = self._generate_rancher_integrator_layer('verify')
        outcome = self._apply_rancher_integrator_layer(verify_layer)

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
            if 'name' in event.params:
                self._stored.cluster_name = event.params['name']
            container = self.unit.get_container('rancher-integrator')
            register_layer = self._generate_rancher_integrator_layer('register')
            outcome = self._apply_rancher_integrator_layer(register_layer)

            if outcome['status'] and outcome['reason'] != 'No change since previous request.':
                event.log('Cluster successfuly registered, trying to fetch the import manifest...')
                found_manifest = False
                count = 0
                while not found_manifest and count < 15:
                    try:
                        import_manifest_contents = container.list_files('/usr/src/app/import_manifest/',
                                                                        pattern='*.yaml')
                    except APIError as err:
                        event.fail('Unable to retrieve manifest file from rancher-integrator. Error: {}'.format(err))
                        unregister_layer = self._generate_rancher_integrator_layer('unregister')
                        outcome = self._apply_rancher_integrator_layer(unregister_layer)
                        return
                    if len(import_manifest_contents) == 1:
                        try:
                            import_manifest = container.pull(import_manifest_contents[0].path).read()
                            self._stored.cluster_name = import_manifest_contents[0].name.split('.yaml')[0]
                        except PathError as err:
                            event.fail('Unable to retrieve manifest file from rancher-integrator. Error: {}'
                                       .format(err))
                            unregister_layer = self._generate_rancher_integrator_layer('unregister')
                            outcome = self._apply_rancher_integrator_layer(unregister_layer)
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
                                'Insufficient permissions to apply import manifest. '
                                'Try: `juju trust {} --scope=cluster`'
                                .format(self.app.name)
                            )
                        else:
                            event.fail('Unable to apply import manifest. ApiException: {}'.format(err))
                        unregister_layer = self._generate_rancher_integrator_layer('unregister')
                        outcome = self._apply_rancher_integrator_layer(unregister_layer)
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
                    unregister_layer = self._generate_rancher_integrator_layer('unregister')
                    outcome = self._apply_rancher_integrator_layer(unregister_layer)
                    return
            else:
                message = outcome['reason'].split('Err -')
                event.fail('Unable to register cluster. Error: {}'.format(message))
                self._stored.cluster_name = None
                self._stored.registered = False
                return

        else:
            event.set_results({
                'result': 'Cluster already registered. Please unregister {} before trying again.'
                          .format(self._stored.cluster_name),
                'name': self._stored.cluster_name
            })

    def _on_unregister_action(self, event):
        """Register the Kubernetes cluster in a Rancher platform.

        Using the configured API connection details, register
        the Kubernetes cluster into the specified Rancher platform.

        """

        if self._stored.registered:
            unregister_layer = self._generate_rancher_integrator_layer('unregister')
            outcome = self._apply_rancher_integrator_layer(unregister_layer)

            if outcome['status']:
                event.log('Successully unregistered cluster from rancher platform.')
                if self._stored.manifest is not None:
                    # add try
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
        else:
            event.fail(message='Cluster is not registered, there is no need to unregister it.')

    def _generate_rancher_integrator_layer(self, command):
        """Returns a Pebble configration layer for rancher-integrator"""

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
        return {
            'summary': 'rancher-integrator layer',
            'description': 'pebble config layer for rancher-integrator',
            'services': {
                'rancher-integrator': {
                    'override': 'replace',
                    'summary': 'rancher-integrator',
                    'command': 'python3 ./rancher-integrator.py ' + command,
                    'startup': 'enabled',
                    'environment': env,
                }
            },
        }

    def _apply_rancher_integrator_layer(self, layer):
        """Applies a Pebble configration layer for rancher-integrator"""

        # Get the rancher-integrator container so we can configure/manipulate it
        container = self.unit.get_container('rancher-integrator')

        # Get the current config
        services = container.get_plan().to_dict().get("services", {})
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
            else:
                return {'status': True, 'reason': 'Change applied.'}
        else:
            return {'status': True, 'reason': 'No change since previous request.'}


if __name__ == "__main__":
    main(RancherIntegratorCharm)
