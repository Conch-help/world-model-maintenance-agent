import json
from wm_maint.sequence_world_model import train_and_evaluate_sequence_model

if __name__ == "__main__":
    print(json.dumps(train_and_evaluate_sequence_model("artifacts/sequence_model_comparison.json"), ensure_ascii=False, indent=2))
