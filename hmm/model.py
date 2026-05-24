from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import numpy as np


class HMMUnavailableError(RuntimeError):
    pass


@dataclass
class HMMFitResult:
    model: Any
    n_states: int
    bic: float
    score: float
    mean: np.ndarray
    std: np.ndarray
    feature_columns: list[str]
    state_order: dict[int, int]


def _load_gaussian_hmm():
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError as exc:
        raise HMMUnavailableError(
            "hmmlearn no esta instalado. Instala dependencias con: pip install hmmlearn"
        ) from exc
    return GaussianHMM


def _standardize(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std = np.where(std == 0, 1.0, std)
    return (matrix - mean) / std, mean, std


def _bic(log_likelihood: float, n_samples: int, n_features: int, n_states: int) -> float:
    # start probabilities + transition matrix + means + diagonal covariances
    params = (n_states - 1) + n_states * (n_states - 1) + n_states * n_features * 2
    return -2.0 * log_likelihood + params * np.log(max(n_samples, 1))


def fit_best_hmm(matrix: np.ndarray, feature_columns: list[str], min_states: int = 2, max_states: int = 5) -> HMMFitResult:
    if matrix.size == 0 or len(matrix) < 100:
        raise ValueError("No hay suficientes muestras para entrenar HMM.")

    GaussianHMM = _load_gaussian_hmm()
    max_train_samples = int(os.getenv("HMM_MAX_TRAIN_SAMPLES", "5000"))
    max_iterations = int(os.getenv("HMM_MAX_ITERATIONS", "300"))
    train_matrix = matrix
    if len(matrix) > max_train_samples > 0:
        step = max(1, len(matrix) // max_train_samples)
        train_matrix = matrix[::step][:max_train_samples]

    scaled, mean, std = _standardize(train_matrix)
    best: HMMFitResult | None = None

    for n_states in range(min_states, max_states + 1):
        model = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            n_iter=max_iterations,
            random_state=42,
            tol=1e-4,
        )
        model.fit(scaled)
        score = float(model.score(scaled))
        bic = _bic(score, len(scaled), scaled.shape[1], n_states)
        raw_states = model.predict(scaled)
        volatility_by_state = {
            state: float(np.std(train_matrix[raw_states == state, 0])) if np.any(raw_states == state) else 0.0
            for state in range(n_states)
        }
        ordered = sorted(volatility_by_state, key=volatility_by_state.get)
        state_order = {raw_state: ordered_state for ordered_state, raw_state in enumerate(ordered)}
        candidate = HMMFitResult(model, n_states, bic, score, mean, std, feature_columns, state_order)
        if best is None or candidate.bic < best.bic:
            best = candidate

    if best is None:
        raise RuntimeError("No se pudo entrenar ningun HMM.")
    return best


def predict_ordered_states(result: HMMFitResult, matrix: np.ndarray) -> np.ndarray:
    scaled = (matrix - result.mean) / result.std
    raw_states = result.model.predict(scaled)
    return np.array([result.state_order[int(state)] for state in raw_states], dtype=int)
