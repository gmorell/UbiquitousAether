from twisted.application import internet
from twisted.application import service
from twisted.internet import task
from twisted.web import resource
from twisted.web import server

import hashlib
import json
import requests

class MFIDevice(object):
    def __init__(self, config_directive):
        if "host" not in config_directive:
            raise ValueError("Missing host Parameter in Config Directive")
        if "username" not in config_directive:
            raise ValueError("Missing Username Parameter in Config Directive")
        if "password" not in config_directive:
            raise ValueError("Missing Password Parameter in Config Directive")

        self.host = config_directive['host']
        self.auth_u = config_directive['username']
        self.auth_p = config_directive['password']

        if "name" not in config_directive:
            self.name = self.host
        else:
            self.name = config_directive['name']

        if "sensors" in config_directive:
            self.sensor_mapping = config_directive['sensors']
        else:
            self.sensor_mapping = {}

        self.cookie = self._gen_airos_cookie()
        self.login()

        self.update_port_status()

        # self.toggle_port(6)

    def _gen_airos_cookie(self):
        value =  hashlib.md5(self.host).hexdigest()
        return {"AIROS_SESSIONID": value}

    def _as_prg_grp(self):
        if self.sensor_mapping:
            l = []
            for k,v in self.sensor_mapping.iteritems():
                if "name" in v:
                    l.append(
                        {
                            "action":"%s.%s" % (self.name, k),
                            "display": v['name'] or k,
                            "color": self.single_port_color_return(k)
                        }
                    )
                else:
                    l.append(
                        {
                            "action":"%s.%s" % (self.name, k),
                            "display": k,
                            "color": self.single_port_color_return(k)
                        }
                    )
            return l
        else:
            pass  # todo return the api

    def _as_prg_list(self):
        l = []
        for k,v in self.sensor_mapping.iteritems():
            l.append("%s.%s" % (self.name, k))

        return l

    def toggle_port(self, port):
        if port in self.sensor_mapping:
            editable = self.sensor_mapping[port].get('editable',True)
            if editable:
                current = self.parsed_status[port]['output']
                if current == 0:
                    target = 1
                else:
                    target = 0

                requests.put("http://%s/sensors/%i" % (self.host, port), cookies=self.cookie, data={"output":target})
                return "changed"

            return "uneditable"
        return "bad"


    def get_port_status(self):
        res = requests.get("http://%s/sensors" % self.host, cookies=self.cookie)
        return res.json()

    def clean_port_status(self):
        sens = self.status['sensors']
        out = {}
        for i in sens:
            if "port" in i:
                out[i['port']] = i

        return out

    def single_port_color_return(self, port):
        state = self.parsed_status[port]
        if state['output'] == 1:
            output = ['#609809', '#609809']
        else:
            output = ["#993400"]

        return output

    def update_port_status(self):
        self.status = self.get_port_status()
        self.parsed_status = self.clean_port_status()

    def login(self):
        # do the login flow
        l = requests.post(
            "http://%s/login.cgi" % self.host,
            data={"username":self.auth_u, "password":self.auth_p},
            cookies=self.cookie
        )

        # check the status
        s = requests.get(
            "http://%s/status.cgi" % self.host,
            cookies=self.cookie
        )

        # if we're logged in it'll return json, else it'll return the HTML login page so there's an easy check here
        try:
            s.json()
        except:
            raise Exception("Username and password didn't work, please check config for `%s`" % self.name)

    def logout(self):
        requests.get(
            "http://%s/logout.cgi" % self.host,
            cookies=self.cookie
        )


class ProgramSetter(resource.Resource):
    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service = service

    def handle_get_post(self, prog):
        if prog:
            val = prog[0]
            if val not in self.service.all_programs().keys():
                return json.dumps(
                    {
                        "status": "ERROR_NON_EXISTENT_PROGRAM_PARAMETER",
                        "value": val
                    }
                )
            else:
                device = self.service.all_programs().get(val, None)
                port = int(val.rsplit(".",1)[1])
                res = device.toggle_port(port)
                if res == "uneditable":
                    return json.dumps(
                        {
                            "status": "ERROR_NOT_ALLOWED_TO_EDIT",
                            "value": val
                        }
                    )
                return json.dumps(
                    {
                        "status": "SUCCESS_CHANGED_PROGRAM",
                        "value": val
                    }
                )
        return json.dumps(
            {
                "status": "ERROR_MISSING_PROGRAM_PARAMETER",
                "value": "prog"
            }
        )

    def render_GET(self, request):
        request.setHeader("Content-Type", "application/json; charset=utf-8")
        prog = request.args.get('prog', None)
        return self.handle_get_post(prog)

    def render_POST(self, request):
        request.setHeader("Content-Type", "application/json; charset=utf-8")
        prog = request.args.get('prog', None)
        return self.handle_get_post(prog)


class ProgramList(resource.Resource):
    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service = service

    def render_GET(self, request):
        request.setHeader("Content-Type", "application/json; charset=utf-8")
        # status = sorted(self.service.available_progs.keys())
        retval = json.dumps({"available_progs": self.service.all_programs().keys()})
        return retval


class ProgramListGrouped(resource.Resource):
    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service = service

    def render_GET(self, request):
        request.setHeader("Content-Type", "application/json; charset=utf-8")
        # grpd = {}
        # for k,v in self.service.available_progs.iteritems():
        #     print k
        #     grouping_val = v.get('grouping')
        #     if grouping_val and grouping_val in grpd:
        #         grpd[grouping_val].append(k)
        #     elif grouping_val:
        #         grpd[grouping_val] = [k]
        #
        # status = sorted(self.service.available_progs.keys())
        retval = json.dumps({"available_grouped": self.service.devices_as_prg_grp()})
        return retval


class UbiquitousService(service.Service):

    def __init__(self, devices, update_freq=5.0):
        self.devices = devices
        self.update_freq = update_freq

        # start the update loop
        self.loop = task.LoopingCall(self.devices_update)
        self.loop.start(self.update_freq)

    def devices_update(self):
        [d.update_port_status() for d in self.devices]

    def device_as_prg_grp(self, d):
        return d._as_prg_grp()

    def devices_as_prg_grp(self):
        return {d.name: self.device_as_prg_grp(d) for d in self.devices}

    def all_programs(self):
        # l = []
        # [l.extend(d._as_prg_list()) for d in self.devices]
        # print [d._as_prg_list() for d in self.devices]
        l = {}
        for d in self.devices:
            ps = d._as_prg_list()
            for p in ps:
                l[p] = d

        print l
        return l

    def getResources(self):
        r = resource.Resource()
        r.putChild("", r)

        se = ProgramSetter(self)
        r.putChild("set", se)

        pl = ProgramList(self)
        r.putChild("progs", pl)

        plg = ProgramListGrouped(self)
        r.putChild("progs_grp", plg)

        return r
#startup
try:
    import config
except:
    raise Exception("No Configuration Created, please see config_example.py for details")


application = service.Application('ubiquitous_aether')  # , uid=1, gid=1)
devices = [MFIDevice(d) for d in config.DEVICES]
uservice = UbiquitousService(devices)
serviceCollection = service.IServiceCollection(application)
uservice.setServiceParent(serviceCollection)
# internet.TCPServer(8660, s.getLightFactory()).setServiceParent(serviceCollection)
internet.TCPServer(8680, server.Site(uservice.getResources())).setServiceParent(serviceCollection)