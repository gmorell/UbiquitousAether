DEVICES = [
    {
        "host":"192.168.1.1",
        "username": "ubnt",
        "password": "ubnt",
        "name": "Living", # no spaces pls, use
        "sensors":{
            1: {
                "name":"Lamp"
            },
            2: {
                "name": None # <- will just show 2
            },
            3:{
                "name":"TV"
            },
            # etc
        }
    },
    {
        "host":"192.168.1.1",
        "username": "ubnt",
        "password": "ubnt",
        "name": "Kitchen",
        "sensors":{
            1: {
                "name":"Rice Cooker"
            },
            2: {
                "name":"Crock Pot"
            },
        }
    },
]

"""
Arguments for sensors
name : name string, if unset, will show number
show : defaults to True, show in UI
editable : defaults to False, controllable via ui # still no support
"""
