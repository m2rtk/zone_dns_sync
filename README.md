# Thing that updates dns entry in zone.ee when your external IP changes

## Usage

```
$ docker run -it -e ZONE_USERNAME=user ZONE_API_KEY=api_key m2rtk/zone_dns_sync --a-record domain:entry_name --interval-seconds 30
```