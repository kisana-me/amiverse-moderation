"""画像レーティング自動判定サービス

NudeNet(ONNX/CPU)で画像内の部位を検出し、4段階のレーティングに割り当てる。
  rejected: 露出した性器・肛門(公開不可の候補。人間の確認前提)
  r18     : 露出した胸・尻
  nsfw    : 下着・水着など覆われた性的部位
  general : 上記なし

POST /classify に画像を複数添付すると、全体判定(最も高いレーティング)と
画像ごとの検出結果を返す。動画は呼び出し側でフレーム分解して送る。
"""

import os
import tempfile

from fastapi import FastAPI, UploadFile, File
from nudenet import NudeDetector

CLASSIFIER_NAME = "nudenet-v3"

RATINGS = ["general", "nsfw", "r18", "rejected"]

# ラベル→レーティングの対応(閾値は環境変数で調整可能)
REJECTED_LABELS = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
}
R18_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "BUTTOCKS_EXPOSED",
}
NSFW_LABELS = {
    "FEMALE_GENITALIA_COVERED",
    "FEMALE_BREAST_COVERED",
    "BUTTOCKS_COVERED",
    "ANUS_COVERED",
}

REJECTED_THRESHOLD = float(os.environ.get("MODERATION_REJECTED_THRESHOLD", "0.65"))
R18_THRESHOLD = float(os.environ.get("MODERATION_R18_THRESHOLD", "0.60"))
NSFW_THRESHOLD = float(os.environ.get("MODERATION_NSFW_THRESHOLD", "0.60"))
# rejected相当のラベルが確信度不足だった場合にr18へ倒すグレーゾーン下限
GREY_THRESHOLD = float(os.environ.get("MODERATION_GREY_THRESHOLD", "0.35"))

app = FastAPI(title="amiverse-moderation")
detector = NudeDetector()


def rate_detections(detections: list[dict]) -> str:
    rating = "general"
    for detection in detections:
        label = detection["class"]
        score = detection["score"]
        if label in REJECTED_LABELS:
            if score >= REJECTED_THRESHOLD:
                return "rejected"
            if score >= GREY_THRESHOLD:
                rating = max(rating, "r18", key=RATINGS.index)
            continue
        if label in R18_LABELS and score >= R18_THRESHOLD:
            rating = max(rating, "r18", key=RATINGS.index)
        elif label in NSFW_LABELS and score >= NSFW_THRESHOLD:
            rating = max(rating, "nsfw", key=RATINGS.index)
    return rating


@app.get("/health")
def health():
    return {"status": "ok", "classifier": CLASSIFIER_NAME}


@app.post("/classify")
async def classify(files: list[UploadFile] = File(...)):
    results = []
    overall = "general"

    for upload in files:
        suffix = os.path.splitext(upload.filename or "")[1] or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await upload.read())
            path = tmp.name

        try:
            detections = detector.detect(path)
        except Exception as error:  # 壊れた画像などは判定不能として扱う
            results.append({"filename": upload.filename, "error": str(error), "rating": "general", "detections": []})
            continue
        finally:
            os.unlink(path)

        rating = rate_detections(detections)
        overall = max(overall, rating, key=RATINGS.index)
        results.append({
            "filename": upload.filename,
            "rating": rating,
            "detections": [
                {"class": d["class"], "score": round(float(d["score"]), 4)}
                for d in detections
                if d["score"] >= 0.3
            ],
        })

    return {
        "rating": overall,
        "classifier": CLASSIFIER_NAME,
        "results": results,
    }
