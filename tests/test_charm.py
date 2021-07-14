# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import patch

from charm import RancherIntegratorCharm
# from ops.model import ActiveStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):

    @patch('charm.Kubernetes')
    def setUp(self, MockKubernetes):
        self.harness = Harness(RancherIntegratorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_generate_rancher_integrator_layer(self):
        self.harness.disable_hooks()
        # Test with default config
        self.assertEqual(self.harness.charm.config['url'], 'changeme')
        self.assertEqual(self.harness.charm.config['bearer-token'], 'change:me')
        self.assertEqual(self.harness.charm.config['cert-verify'], 'True')
        self.assertEqual(self.harness.charm._stored.cluster_name, None)

        env = {
            'RANCHER_INTEGRATOR_WAIT': 'True',
            'RANCHER_INTEGRATOR_CERT_CHECK': 'True',
            'RANCHER_INTEGRATOR_URL': 'changeme',
            'RANCHER_INTEGRATOR_USERNAME': 'change',
            'RANCHER_INTEGRATOR_PASSWORD': 'me'
        }

        expected = {
            'summary': 'rancher-integrator layer',
            'description': 'pebble config layer for rancher-integrator',
            'services': {
                'rancher-integrator': {
                    'override': 'replace',
                    'summary': 'rancher-integrator',
                    'command': 'python3 ./rancher-integrator.py verify',
                    'startup': 'enabled',
                    'environment': env,
                }
            },
        }
        self.assertEqual(self.harness.charm._generate_rancher_integrator_layer('verify'), expected)

        # Test format of bearer token
        self.harness.update_config({'bearer-token': 'nocolon'})
        expected['services']['rancher-integrator']['environment'].pop('RANCHER_INTEGRATOR_USERNAME')
        expected['services']['rancher-integrator']['environment'].pop('RANCHER_INTEGRATOR_PASSWORD')
        self.assertEqual(self.harness.charm._generate_rancher_integrator_layer('verify'), expected)

        # Test disable cert-verify
        self.harness.update_config({'cert-verify': 'False'})
        expected['services']['rancher-integrator']['environment']['RANCHER_INTEGRATOR_CERT_CHECK'] = 'False'
        self.assertEqual(self.harness.charm._generate_rancher_integrator_layer('verify'), expected)

        # Test setting cluster name environment variable
        self.harness.charm._stored.cluster_name = 'test_cluster'
        (expected['services']
                 ['rancher-integrator']
                 ['environment']
                 ['RANCHER_INTEGRATOR_CLUSTER_NAME']) = 'test_cluster'
        self.assertEqual(self.harness.charm._generate_rancher_integrator_layer('verify'), expected)
