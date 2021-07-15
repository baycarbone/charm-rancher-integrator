# Rancher Integrator

## Description

This charm deploys and manages the rancher-integration application capable of registering (and if 
needed unregistering) a Kubernetes cluster within an existing Rancher container management 
platform.  
  
As a result of the cluster import process, the Rancher platform generates an import manifest which 
is fetched and stored by the rancher-integrator application.  

To finalize the registration process, the sidecar charm will retrieve the import manifest and 
apply it on the Kubernetes cluster hosting the charm.

Charmhub page: https://charmhub.io/rancher-integrator  
Documentation: https://charmhub.io/rancher-integrator/docs  
Bugs / Issues: https://github.com/baycarbone/charm-rancher-integrator/issues

More information regarding the rancher-interator application can be found at 
[rancher-integrator repository](https://github.com/baycarbone/rancher-integrator).

More information about the cluster registration process can be found at:  
https://rancher.com/docs/rancher/v2.5/en/cluster-provisioning/registered-clusters/

## Quickstart

Assuming you have juju installed and bootstrapped on a Kubernetes cluster, deploy the charm and 
execute the required actions as needed (if you do not, please [setup](#development-setup)).

In order to execute the actions the following config options need to be set:
- url: url of the existing Rancher platform against which registration will be performed.

- bearer-token: bearer-token needed to access the Rancher api. For more information on retrieving
such a token, please see [rancher-api-keys](https://rancher.com/docs/rancher/v2.5/en/user-settings/api-keys/).

- (optional) cert-verify: toggles verification of the Rancher platform certificate. Setting this to
 'False' is not recommended but can be useful for development purposes when using a self-signed 
 certificate.

```bash
# Deploy the rancher-integrator charm
$ juju deploy rancher-integrator --channel beta \
  --config url="cluster.test" \
  --config bearer-token="token-abcde:abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzab"

# Elavate permisions in order for the charm to communicate with the Kubernetes API
$ juju trust rancher-integrator --scope=cluster

# Wait for the deployment to complete. The rancher-integrator unit should be in 'active idle' 
# state and its message should inform you that the cluster is currently not registered.
$ watch -n1 --color juju status --color

# Execute the registration action using actions-v2 for a better UX
export JUJU_FEATURES=actions-v2
$ juju run rancher-integrator/0 register --format=yaml
```

### Actions

**register**  
Request the rancher-integration application to register the Kubernetes cluster, then retrieve 
the import manifest and apply it on the Kubernetes cluster hosting the charm.

> **_Note:_**  
The register action takes an optional ```name``` parameter when a user defined cluster name 
within the Rancher platform is desired. If this parameter is not set, a randomly generated cluster 
name will be assigned and returned to the user.

**unregister**  
Request the rancher-integration application to unregister the Kubernetes cluster, then delete the 
import manifest from the Kubernetes cluster hosting the charm.

## Development Setup

To set up a local test environment with [MicroK8s](https://microk8s.io):

```bash
# Install MicroK8s
$ sudo snap install --classic microk8s

# Wait for MicroK8s to be ready
$ sudo microk8s status --wait-ready

# Enable features required by Juju controller & charm
$ sudo microk8s enable storage dns ingress rbac

# (Optional) Alias kubectl bundled with MicroK8s package
$ sudo snap alias microk8s.kubectl kubectl

# (Optional) Add current user to 'microk8s' group
# This avoid needing to use 'sudo' with the 'microk8s' command
$ sudo usermod -aG microk8s $(whoami)

# Activate the new group (in the current shell only)
# Log out and log back in to make the change system-wide
$ newgrp microk8s

# Install Charmcraft
$ sudo snap install charmcraft

# Install juju
$ sudo snap install --classic juju

# Bootstrap the Juju controller on MicroK8s
$ juju bootstrap microk8s micro

# Add a new model to Juju
$ juju add-model development
```

## Build and Deploy Locally

```bash
# Clone the charm code
$ git clone https://github.com/baycarbone/charm-rancher-integrator && cd charm-rancher-integrator

# Build the charm package
$ charmcraft pack

# Deploy!
$ juju deploy ./rancher-integrator.charm --resource rancher-integrator-image=baycarbone/rancher-integrator:latest

# Set required config options
$ juju config rancher-integrator url=<rancher url>
$ juju config rancher-integrator bearer-token=<rancher api token>
$ juju config rancher-integrator cert-verify=<'True'|'False'>

# Elavate permisions in order for the charm to communicate with the Kubernetes API
$ juju trust rancher-integrator --scope=cluster

# Wait for the deployment to complete
$ watch -n1 --color juju status --color

# Execute actions using actions-v2 for a better UX e.g:
export JUJU_FEATURES=actions-v2
$ juju run rancher-integrator/0 register --format=yaml
$ juju run rancher-integrator/0 unregister --format=yaml
$ juju run rancher-integrator/0 register name=<name> --format=yaml
```

## Testing

```bash
# Clone the charm code
$ git clone https://github.com/baycarbone/charm-rancher-integrator && cd charm-rancher-integrator

# Create a virtual environemnt for the charm code
$ python3 -m venv venv

# Activate the venv
$ source ./venv/bin/activate

# Install dependencies
$ pip install -r requirements-dev.txt

# Run the tests
$ ./run_tests
```