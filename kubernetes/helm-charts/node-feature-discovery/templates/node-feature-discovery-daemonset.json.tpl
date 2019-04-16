{
  "apiVersion": "apps/v1",
  "kind": "DaemonSet",
  "metadata": {
    "labels": {
      "app": "node-feature-discovery"
    },
    "name": "node-feature-discovery"
  },
  "spec": {
    "selector": {
      "matchLabels": {
        "app": "node-feature-discovery"
      }
    },
    "template": {
      "metadata": {
        "labels": {
          "app": "node-feature-discovery"
        }
      },
      "spec": {
        "hostNetwork": true,
        "serviceAccount": "node-feature-discovery",
        "containers": [
          {
            "env": [
              {
                "name": "NODE_NAME",
                "valueFrom": {
                  "fieldRef": {
                    "fieldPath": "spec.nodeName"
                  }
                }
              }
            ],
            "image": "quay.io/kubernetes_incubator/node-feature-discovery:v0.3.0",
            "name": "node-feature-discovery",
            "args": ["--sleep-interval=60s"],
            "volumeMounts": [
              {
                "name": "host-sys",
                "mountPath": "/host-sys"
              }
            ]
          }
        ],
        "volumes": [
          {
            "name": "host-sys",
            "hostPath": {
              "path": "/sys"
            }
          }
        ]
      }
    }
  }
}
