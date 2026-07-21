from phase6.trainer import Trainer, TrainingError
from phase6.config import Config
from phase6.types import TrainingStatus


class DummyModelEpoch:
    def __init__(self):
        self.epochs_run = 0

    def train_epoch(self, train_loader):
        # simulate training by counting batches
        self.epochs_run += 1
        return 0.5  # dummy loss

    def predict_topk(self, inputs, k):
        # return a list of predictions matching inputs length
        n = len(inputs)
        return [[0] * k for _ in range(n)]

    def predict_probs(self, inputs):
        n = len(inputs)
        return [[1.0] + [0.0] * (1) for _ in range(n)]


def make_train_loader():
    return [{"inputs": [1, 2], "targets": [2]}, {"inputs": [3], "targets": [3]}]


def test_trainer_runs_epochs():
    cfg = Config(epochs=2, checkpoint_interval_epochs=100, max_checkpoints=0)
    model_spec = object()
    trainer = Trainer(model_spec=model_spec, config=cfg)
    model = DummyModelEpoch()

    result = trainer.train(model, train_loader=make_train_loader(), val_loader=None)
    assert result.status == TrainingStatus.COMPLETED
    assert result.num_epochs_run == 2


def test_trainer_missing_model_api_raises():
    cfg = Config(epochs=1)
    trainer = Trainer(model_spec=object(), config=cfg)

    class BadModel:
        pass

    try:
        trainer.train(BadModel(), train_loader=[])  # type: ignore[arg-type]
        assert False, "TrainingError expected"
    except TrainingError:
        pass
