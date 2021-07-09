# Rancher Integrator

## Description

This charm deploys and manages the rancher-integration application capable of registering (and if
needed unregistering) the Kubernetes cluster hosting the charm within an existing Rancher container
 management platform.

Charmhub page: https://charmhub.io/rancher-integrator  
Documentation: https://charmhub.io/rancher-integrator/docs  
Bugs / Issues: https://github.com/baycarbone/charm-rancher-integrator/issues

More information regarding the rancher-interator application can be found at [rancher-integrator repository](https://github.com/baycarbone/rancher-integrator).

## Quickstart

Assuming you have juju installed and bootstrapped on a Kubernetes cluster, deploy the charm and
execute the required actions as needed (if you do not, see the next section).

In order to execute the actions the following config options need to be set:
- url: url of the existing Rancher platform against which registration will be performed.

- bearer-token: bearer-token needed to access the Rancher api. For more information on retrieving
such a token, please see [rancher-api-keys](https://rancher.com/docs/rancher/v2.5/en/user-settings/api-keys/).

- (optional) cluster-name: useful if you want a user defined cluster name within the Rancher platform. If this
option is not set, a randomly generated cluster name will be assigned.

- (optional) cert-verify: toggles verification of the Rancher platform certificate. Setting this to
 false is not recommended but can be useful for development purposes when using a self-signed 
 certificate.

```bash
# Deploy the rancher-integrator charm
$ juju deploy rancher-integrator \
  --config url="cluster.test" \
  --config bearer-token="token-abcde:abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzab"

# Elavate permisions in order for the charm to communicate with the Kubernetes API
$ juju trust rancher-integrator --scope=cluster

# Wait for the deployment to complete
$ watch -n1 --color juju status --color

# Execute the registration action
$ juju run-action rancher-integrator/0 register
```

## Developing

Create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests
