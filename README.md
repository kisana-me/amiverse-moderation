# amiverse-moderation

画像のレーティングを自動判定するAPIサービスです。
NudeNet(ONNX)を使用し、CPUのみで動作します。

## レーティング

| rating | 意味 |
|---|---|
| `general` | 通常 |
| `nsfw` | センシティブ(注意喚起) |
| `r18` | 成人向け |
| `rejected` | 公開不可の候補(人間による確認を推奨) |

## 判定ロジック

部位検出の結果をレーティングにマッピングします。閾値は環境変数で調整できます。

| 検出 | レーティング | 閾値(env) |
|---|---|---|
| 露出した性器・肛門 | rejected | `MODERATION_REJECTED_THRESHOLD` (0.65) |
| 同・確信度がグレーゾーン | r18 に降格 | `MODERATION_GREY_THRESHOLD` (0.35) |
| 露出した胸・尻 | r18 | `MODERATION_R18_THRESHOLD` (0.60) |
| 覆われた性的部位(下着等) | nsfw | `MODERATION_NSFW_THRESHOLD` (0.60) |
| その他 | general | - |

- 動画は呼び出し側でフレームに分解して送り、最も高いレーティングを採用する想定です
- 写真向けのモデルのため、イラスト・線画の判定精度は低めです。閾値調整と通報運用で補完してください
- 自動判定はあくまで一次判定です。`rejected` の確定は人間の確認を挟むことを推奨します

## API

```
GET  /health
  → {"status":"ok","classifier":"nudenet-v3"}

POST /classify          multipart: files=画像(複数可)
  → {"rating":"nsfw","classifier":"nudenet-v3","results":[{filename, rating, detections:[{class, score}]}]}
```

## 起動

```
docker build -t amiverse-moderation .
docker run -p 8000:8000 amiverse-moderation
```
