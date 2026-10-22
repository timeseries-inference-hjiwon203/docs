# 과제 1 수집 코드

<!-- 수정 기록
- 2026-10-22 처음 작성: Mac `timeseries-inference` 폴더의 과제 1 코드를 docs 저장소로 옮기며 안내 추가
-->

aip-1(Jetson)의 `/home/jiwon/collector/`에 두고 돌리는 코드다. 비밀번호와 토큰은 같은 폴더의 `.env`에만 있고 이 저장소에는 없다.

| 파일 | 하는 일 |
|---|---|
| `mqtt_collector.py` | **지금 쓰는 수집기.** MQTT로 센서 메시지를 받아 aip-1 InfluxDB `jiwon` 버킷에 쓴다. 켜질 때 끊긴 동안의 빈 구간은 운영진 DB에서 채운다 |
| `jiwon-mqtt.service` | `mqtt_collector.py`를 항상 켜 두는 systemd 설정 (죽으면 30초 뒤 다시 켬) |
| `sync.py` | 예전 수집기. 운영진 InfluxDB에서 1분마다 복사한다. 지금은 꺼 두고 예비로 남김 |
| `jiwon-collector.service`, `jiwon-collector.timer` | `sync.py`를 1분마다 돌리는 systemd 설정 (지금 꺼짐) |
| `status.py` | 버킷에 쌓인 양, 마지막 시각, 빈 구간을 보여 준다 |
| `verify.py` | 원본과 내 버킷의 건수를 비교해 빠진 게 없는지 확인한다 |
| `config.json` | 주소, 버킷, 공간·항목, MQTT 설정 |

`.env`에 들어가는 환경 변수: `MQTT_PW`, `STAFF_TOKEN`, `MY_TOKEN`. 값은 git에 올리지 않는다.

주의: `jiwon-collector.timer`와 `jiwon-mqtt.service`를 동시에 켜지 않는다(같은 데이터를 두 번 씀).
