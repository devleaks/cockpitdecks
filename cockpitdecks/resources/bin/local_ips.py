from netifaces import interfaces, ifaddresses, AF_INET

# https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib/


def get_local_addresses():
    ips = {}
    for ifaceName in interfaces():
        ips[ifaceName] = [i["addr"] for i in ifaddresses(ifaceName).setdefault(AF_INET, [{"addr": "No IP addr"}])]
    return ips


def get_local_ips():
    ret = []
    for k, v in get_local_addresses().items():
        for a in v:
            if a.startswith("192"):
                ret.append(a)
    return ret


print(get_local_addresses())
print(get_local_ips())
