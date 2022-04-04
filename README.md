# Thing that updates dns entry in zone.ee when your external IP changes

## Usage

```
$ docker run -it \
  -e ZONE_USERNAME=user \
  -e ZONE_API_KEY=api_key \
  m2rtk/zone-dns-sync \
  --a-record=domain:entry_name \
  --zone-cache-ttl-seconds=1800 \
  --interval-seconds=30
```