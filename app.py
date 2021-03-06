import requests
import base64
import os
import time
import logging
import sys
from dataclasses import dataclass
from cachetools import TTLCache

logging.basicConfig(
    stream=sys.stdout,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    level=logging.INFO
)


def get_external_ip() -> str:
    url = 'https://api.ipify.org'
    response = requests.get(url)
    response.raise_for_status()
    ip = response.text

    logging.info(f"GET {url} -> {ip}")

    return ip


class Zone:
    def __init__(self,
                 zone_username,
                 zone_api_key,
                 base_url='https://api.zone.eu/v2',
                 cache_ttl=1800):
        self.basic_auth = "Basic " + base64.b64encode((zone_username + ':' + zone_api_key).encode()).decode('utf8')
        self.base_url = base_url
        self.cache = TTLCache(maxsize=1000, ttl=cache_ttl)

    def get_dns_a_records(self, domain):
        if domain not in self.cache:
            url = f"{self.base_url}/dns/{domain}/a"
            logging.info(f"GET {url}")
            response = requests.get(url, headers={'Authorization': self.basic_auth})
            response.raise_for_status()
            self.cache[domain] = list(map(lambda x: A(self, domain, x['id'], x['name'], x['destination']), response.json()))

        return self.cache[domain]

    def get_dns_a_record(self, domain, name):
        records = self.get_dns_a_records(domain)

        for record in records:
            if record.name == name:
                return record

        return None


class A:
    def __init__(self, zone, domain, id, name, destination):
        self.zone = zone
        self.domain = domain
        self.id = id
        self.name = name
        self.destination = destination

    def update(self, destination):
        url = f"{self.zone.base_url}/dns/{self.domain}/a/{self.id}"
        logging.debug(f"PUT {url} {self.name} {destination}")
        response = requests.put(
            url,
            json={'name': self.name, 'destination': destination},
            headers={'Authorization': self.zone.basic_auth}
        )
        response.raise_for_status()

        data = response.json()[0]

        self.name = data['name']
        self.id = data['id']
        self.destination = data['destination']
        logging.info(f"PUT {url} {self.name} {destination} -> OK")


class OneOneOneOne:
    def __init__(self):
        self.base_url = "https://1.1.1.1/api/v1"
        pass

    def flush(self, domain):
        url = f"{self.base_url}/purge?domain={domain}&type=A"
        logging.debug(f"POST {url}")
        response = requests.post(url)
        response.raise_for_status()
        logging.info(f"POST {url} -> OK")


def env(key) -> str:
    value = os.getenv(key)
    if not value:
        logging.info(f"Missing env var {key}")
        exit(1)
    return value


@dataclass
class ARecordDto:
    domain: str
    name: str
    flushable_domain: str

    @staticmethod
    def parse(s):
        split = s.split(':', 3)

        if len(split) == 3:
            flushable_domain = split[2]
        else:
            flushable_domain = None

        return ARecordDto(split[0], split[1], flushable_domain)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--interval-seconds', type=int, default=10, help='How often to check for external IP')
    parser.add_argument('--zone-cache-ttl-seconds', type=int, default=1800, help='How long to cache records fetched from zone.ee')
    parser.add_argument('--a-record', dest='a_records', action='append', type=ARecordDto.parse, help="A record to update when IP changes. Example: 'm2rt.eu:*.m2rt.eu'. Can be specified multiple times.")

    args, unknown = parser.parse_known_args()

    if not args.a_records:
        parser.error("At least 1 A record required. Use '--a-record domain:name'")

    zone = Zone(env('ZONE_USERNAME'), env('ZONE_API_KEY'), cache_ttl=args.zone_cache_ttl_seconds)
    one_one_one_one = OneOneOneOne()

    while True:
        try:
            external_ip = get_external_ip()

            for input_a_record in args.a_records:
                record = zone.get_dns_a_record(input_a_record.domain, input_a_record.name)

                if external_ip != record.destination:
                    logging.info(f"IP does not match with {record.domain} {record.name} {record.destination}")
                    record.update(external_ip)

                    if input_a_record.flushable_domain:
                        one_one_one_one.flush(input_a_record.flushable_domain)

                else:
                    logging.info(f"IP matches with {record.domain} {record.name}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logging.error("Invalid zone credentials")
                exit(1)
        except Exception as e:
            print(type(e))
            logging.error(e)

        time.sleep(args.interval_seconds)
