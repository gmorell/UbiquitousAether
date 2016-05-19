# Ansible

## (A work in progress)

In here are some ansible bits and pieces to provision a raspi with the correct bits and pieces.

```
ansible-playbook provision.yml -i inventory
```

## Supported LAMBENTCONNECT variables

- `"espudp://192.168.1.1:192.168.1.2"`
- `"adlserial:///dev/ttyACM0"`
- `"debug://"`