from abc import ABCMeta, abstractmethod
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Union, cast

import numpy as np

import sklearn.metrics
from sklearn.utils.multiclass import type_of_target

from smac.utils.constants import MAXINT

from autosklearn.constants import (
    BINARY_CLASSIFICATION, MULTICLASS_CLASSIFICATION, MULTILABEL_CLASSIFICATION,
    MULTIOUTPUT_REGRESSION, REGRESSION, REGRESSION_TASKS, TASK_TYPES,
)

from .util import sanitize_array


class Scorer(object, metaclass=ABCMeta):
    def __init__(
        self,
        name: str,
        score_func: Callable,
        optimum: float,
        worst_possible_result: float,
        sign: float,
        kwargs: Any
    ) -> None:
        self.name = name
        self._kwargs = kwargs
        self._score_func = score_func
        self._optimum = optimum
        self._worst_possible_result = worst_possible_result
        self._sign = sign

    @abstractmethod
    def __call__(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        sample_weight: Optional[List[float]] = None
    ) -> float:
        pass

    def __repr__(self) -> str:
        return self.name


class _PredictScorer(Scorer):
    def __call__(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        sample_weight: Optional[List[float]] = None
    ) -> float:
        """Evaluate predicted target values for X relative to y_true.

        Parameters
        ----------
        y_true : array-like
            Gold standard target values for X.

        y_pred : array-like, [n_samples x n_classes]
            Model predictions

        sample_weight : array-like, optional (default=None)
            Sample weights.

        Returns
        -------
        score : float
            Score function applied to prediction of estimator on X.
        """
        type_true = type_of_target(y_true)
        if type_true == 'binary' and type_of_target(y_pred) == 'continuous' and \
                len(y_pred.shape) == 1:
            # For a pred scorer, no threshold, nor probability is required
            # If y_true is binary, and y_pred is continuous
            # it means that a rounding is necessary to obtain the binary class
            y_pred = np.around(y_pred, decimals=0)
        elif len(y_pred.shape) == 1 or y_pred.shape[1] == 1 or \
                type_true == 'continuous':
            # must be regression, all other task types would return at least
            # two probabilities
            pass
        elif type_true in ['binary', 'multiclass']:
            y_pred = np.argmax(y_pred, axis=1)
        elif type_true == 'multilabel-indicator':
            y_pred[y_pred > 0.5] = 1.0
            y_pred[y_pred <= 0.5] = 0.0
        elif type_true == 'continuous-multioutput':
            pass
        else:
            raise ValueError(type_true)

        if sample_weight is not None:
            return self._sign * self._score_func(y_true, y_pred,
                                                 sample_weight=sample_weight,
                                                 **self._kwargs)
        else:
            return self._sign * self._score_func(y_true, y_pred,
                                                 **self._kwargs)


class _ProbaScorer(Scorer):
    def __call__(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        sample_weight: Optional[List[float]] = None
    ) -> float:
        """Evaluate predicted probabilities for X relative to y_true.
        Parameters
        ----------
        y_true : array-like
            Gold standard target values for X. These must be class labels,
            not probabilities.

        y_pred : array-like, [n_samples x n_classes]
            Model predictions

        sample_weight : array-like, optional (default=None)
            Sample weights.

        Returns
        -------
        score : float
            Score function applied to prediction of estimator on X.
        """

        if self._score_func is sklearn.metrics.log_loss:
            n_labels_pred = np.array(y_pred).reshape((len(y_pred), -1)).shape[1]
            n_labels_test = len(np.unique(y_true))
            if n_labels_pred != n_labels_test:
                labels = list(range(n_labels_pred))
                if sample_weight is not None:
                    return self._sign * self._score_func(y_true, y_pred,
                                                         sample_weight=sample_weight,
                                                         labels=labels,
                                                         **self._kwargs)
                else:
                    return self._sign * self._score_func(y_true, y_pred,
                                                         labels=labels, **self._kwargs)

        if sample_weight is not None:
            return self._sign * self._score_func(y_true, y_pred,
                                                 sample_weight=sample_weight,
                                                 **self._kwargs)
        else:
            return self._sign * self._score_func(y_true, y_pred,
                                                 **self._kwargs)


class _ThresholdScorer(Scorer):
    def __call__(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        sample_weight: Optional[List[float]] = None
    ) -> float:
        """Evaluate decision function output for X relative to y_true.
        Parameters
        ----------
        y_true : array-like
            Gold standard target values for X. These must be class labels,
            not probabilities.

        y_pred : array-like, [n_samples x n_classes]
            Model predictions

        sample_weight : array-like, optional (default=None)
            Sample weights.

        Returns
        -------
        score : float
            Score function applied to prediction of estimator on X.
        """
        y_type = type_of_target(y_true)
        if y_type not in ("binary", "multilabel-indicator"):
            raise ValueError("{0} format is not supported".format(y_type))

        if y_type == "binary":
            if y_pred.ndim > 1:
                y_pred = y_pred[:, 1]
        elif isinstance(y_pred, list):
            y_pred = np.vstack([p[:, -1] for p in y_pred]).T

        if sample_weight is not None:
            return self._sign * self._score_func(y_true, y_pred,
                                                 sample_weight=sample_weight,
                                                 **self._kwargs)
        else:
            return self._sign * self._score_func(y_true, y_pred, **self._kwargs)


def make_scorer(
    name: str,
    score_func: Callable,
    optimum: float = 1.0,
    worst_possible_result: float = 0.0,
    greater_is_better: bool = True,
    needs_proba: bool = False,
    needs_threshold: bool = False,
    **kwargs: Any
) -> Scorer:
    """Make a scorer from a performance metric or loss function.

    Factory inspired by scikit-learn which wraps scikit-learn scoring functions
    to be used in auto-sklearn.

    Parameters
    ----------
    score_func : callable
        Score function (or loss function) with signature
        ``score_func(y, y_pred, **kwargs)``.

    optimum : int or float, default=1
        The best score achievable by the score function, i.e. maximum in case of
        scorer function and minimum in case of loss function.

    greater_is_better : boolean, default=True
        Whether score_func is a score function (default), meaning high is good,
        or a loss function, meaning low is good. In the latter case, the
        scorer object will sign-flip the outcome of the score_func.

    needs_proba : boolean, default=False
        Whether score_func requires predict_proba to get probability estimates
        out of a classifier.

    needs_threshold : boolean, default=False
        Whether score_func takes a continuous decision certainty.
        This only works for binary classification.

    **kwargs : additional arguments
        Additional parameters to be passed to score_func.

    Returns
    -------
    scorer : callable
        Callable object that returns a scalar score; greater is better.
    """
    sign = 1 if greater_is_better else -1
    if needs_proba:
        return _ProbaScorer(name, score_func, optimum, worst_possible_result, sign, kwargs)
    elif needs_threshold:
        return _ThresholdScorer(name, score_func, optimum, worst_possible_result, sign, kwargs)
    else:
        return _PredictScorer(name, score_func, optimum, worst_possible_result, sign, kwargs)


# Standard regression scores
mean_absolute_error = make_scorer('mean_absolute_error',
                                  sklearn.metrics.mean_absolute_error,
                                  optimum=0,
                                  worst_possible_result=MAXINT,
                                  greater_is_better=False)
mean_squared_error = make_scorer('mean_squared_error',
                                 sklearn.metrics.mean_squared_error,
                                 optimum=0,
                                 worst_possible_result=MAXINT,
                                 greater_is_better=False,
                                 squared=True)
root_mean_squared_error = make_scorer('root_mean_squared_error',
                                      sklearn.metrics.mean_squared_error,
                                      optimum=0,
                                      worst_possible_result=MAXINT,
                                      greater_is_better=False,
                                      squared=False)
mean_squared_log_error = make_scorer('mean_squared_log_error',
                                     sklearn.metrics.mean_squared_log_error,
                                     optimum=0,
                                     worst_possible_result=MAXINT,
                                     greater_is_better=False,)
median_absolute_error = make_scorer('median_absolute_error',
                                    sklearn.metrics.median_absolute_error,
                                    optimum=0,
                                    worst_possible_result=MAXINT,
                                    greater_is_better=False)
r2 = make_scorer('r2',
                 sklearn.metrics.r2_score)

# Standard Classification Scores
accuracy = make_scorer('accuracy',
                       sklearn.metrics.accuracy_score)
balanced_accuracy = make_scorer('balanced_accuracy',
                                sklearn.metrics.balanced_accuracy_score)
f1 = make_scorer('f1',
                 sklearn.metrics.f1_score)

# Score functions that need decision values
roc_auc = make_scorer('roc_auc',
                      sklearn.metrics.roc_auc_score,
                      greater_is_better=True,
                      needs_threshold=True)
average_precision = make_scorer('average_precision',
                                sklearn.metrics.average_precision_score,
                                needs_threshold=True)
precision = make_scorer('precision',
                        sklearn.metrics.precision_score)
recall = make_scorer('recall',
                     sklearn.metrics.recall_score)

# Score function for probabilistic classification
log_loss = make_scorer('log_loss',
                       sklearn.metrics.log_loss,
                       optimum=0,
                       worst_possible_result=MAXINT,
                       greater_is_better=False,
                       needs_proba=True)
# TODO what about mathews correlation coefficient etc?


REGRESSION_METRICS = dict()
for scorer in [mean_absolute_error, mean_squared_error, root_mean_squared_error,
               mean_squared_log_error, median_absolute_error, r2]:
    REGRESSION_METRICS[scorer.name] = scorer

CLASSIFICATION_METRICS = dict()

for scorer in [accuracy, balanced_accuracy, roc_auc, average_precision,
               log_loss]:
    CLASSIFICATION_METRICS[scorer.name] = scorer

for name, metric in [('precision', sklearn.metrics.precision_score),
                     ('recall', sklearn.metrics.recall_score),
                     ('f1', sklearn.metrics.f1_score)]:
    globals()[name] = make_scorer(name, metric)
    CLASSIFICATION_METRICS[name] = globals()[name]
    for average in ['macro', 'micro', 'samples', 'weighted']:
        qualified_name = '{0}_{1}'.format(name, average)
        globals()[qualified_name] = make_scorer(qualified_name,
                                                partial(metric,
                                                        pos_label=None,
                                                        average=average))
        CLASSIFICATION_METRICS[qualified_name] = globals()[qualified_name]


def calculate_score(
    solution: np.ndarray,
    prediction: np.ndarray,
    task_type: int,
    metric: Scorer,
    scoring_functions: Optional[List[Scorer]] = None
) -> Union[float, Dict[str, float]]:
    """
    Returns a score (a magnitude that allows casting the
    optimization problem as a maximization one) for the
    given Auto-Sklearn Scorer object

    Parameters
    ----------
    solution: np.ndarray
        The ground truth of the targets
    prediction: np.ndarray
        The best estimate from the model, of the given targets
    task_type: int
        To understand if the problem task is classification
        or regression
    metric: Scorer
        Object that host a function to calculate how good the
        prediction is according to the solution.
    scoring_functions: List[Scorer]
        A list of metrics to calculate multiple losses
    Returns
    -------
    float or Dict[str, float]
    """
    if task_type not in TASK_TYPES:
        raise NotImplementedError(task_type)

    if scoring_functions:
        score_dict = dict()
        if task_type in REGRESSION_TASKS:
            for metric_ in scoring_functions + [metric]:

                try:
                    score_dict[metric_.name] = _compute_scorer(
                        metric_, prediction, solution, task_type)
                except ValueError as e:
                    print(e, e.args[0])
                    if e.args[0] == "Mean Squared Logarithmic Error cannot be used when " \
                                    "targets contain negative values.":
                        continue
                    else:
                        raise e

        else:
            for metric_ in scoring_functions + [metric]:

                # TODO maybe annotate metrics to define which cases they can
                # handle?

                try:
                    score_dict[metric_.name] = _compute_scorer(
                        metric_, prediction, solution, task_type)
                except ValueError as e:
                    if e.args[0] == 'multiclass format is not supported':
                        continue
                    elif e.args[0] == "Samplewise metrics are not available "\
                            "outside of multilabel classification.":
                        continue
                    elif e.args[0] == "Target is multiclass but "\
                            "average='binary'. Please choose another average "\
                            "setting, one of [None, 'micro', 'macro', 'weighted'].":
                        continue
                    else:
                        raise e

        return score_dict

    else:
        return _compute_scorer(metric, prediction, solution, task_type)


def calculate_loss(
    solution: np.ndarray,
    prediction: np.ndarray,
    task_type: int,
    metric: Scorer,
    scoring_functions: Optional[List[Scorer]] = None
) -> Union[float, Dict[str, float]]:
    """
    Returns a loss (a magnitude that allows casting the
    optimization problem as a minimization one) for the
    given Auto-Sklearn Scorer object

    Parameters
    ----------
    solution: np.ndarray
        The ground truth of the targets
    prediction: np.ndarray
        The best estimate from the model, of the given targets
    task_type: int
        To understand if the problem task is classification
        or regression
    metric: Scorer
        Object that host a function to calculate how good the
        prediction is according to the solution.
    scoring_functions: List[Scorer]
        A list of metrics to calculate multiple losses

    Returns
    -------
    float or Dict[str, float]
        A loss function for each of the provided scorer objects
    """
    score = calculate_score(
        solution=solution,
        prediction=prediction,
        task_type=task_type,
        metric=metric,
        scoring_functions=scoring_functions,
    )

    if scoring_functions:
        score = cast(Dict, score)
        # we expect a dict() object for which we should calculate the loss
        loss_dict = dict()
        for metric_ in scoring_functions + [metric]:
            # TODO: When metrics are annotated with type_of_target support
            # we can remove this check
            if metric_.name not in score:
                continue
            # maybe metric argument is not in scoring_functions
            # so append it to the list. Rather than check if such
            # is the case, redefining loss_dict[metric] is less expensive
            loss_dict[metric_.name] = metric_._optimum - score[metric_.name]
        return loss_dict
    else:
        rval = metric._optimum - cast(float, score)
        return rval


def calculate_metric(
    metric: Scorer,
    prediction: np.ndarray,
    solution: np.ndarray,
    task_type: int
) -> float:
    """
    Returns a metric for the given Auto-Sklearn Scorer object.
    It's direction is determined by the metric itself.

    Parameters
    ----------
    solution: np.ndarray
        The ground truth of the targets
    prediction: np.ndarray
        The best estimate from the model, of the given targets
    task_type: int
        To understand if the problem task is classification
        or regression
    metric: Scorer
        Object that host a function to calculate how good the
        prediction is according to the solution.

    Returns
    -------
    float
    """
    score = _compute_scorer(
        solution=solution,
        prediction=prediction,
        metric=metric,
        task_type=task_type,
    )
    return metric._sign * score


def _compute_scorer(
    metric: Scorer,
    prediction: np.ndarray,
    solution: np.ndarray,
    task_type: int
) -> float:
    """
    Returns a score (a magnitude that allows casting the
    optimization problem as a maximization one) for the
    given Auto-Sklearn Scorer object

    Parameters
    ----------
    solution: np.ndarray
        The ground truth of the targets
    prediction: np.ndarray
        The best estimate from the model, of the given targets
    task_type: int
        To understand if the problem task is classification
        or regression
    metric: Scorer
        Object that host a function to calculate how good the
        prediction is according to the solution.
    Returns
    -------
    float
    """
    if task_type in REGRESSION_TASKS:
        # TODO put this into the regression metric itself
        cprediction = sanitize_array(prediction)
        score = metric(solution, cprediction)
    else:
        score = metric(solution, prediction)
    return score


# Must be at bottom so all metrics are defined
default_metric_for_task: Dict[int, Scorer] = {
    BINARY_CLASSIFICATION: CLASSIFICATION_METRICS['accuracy'],
    MULTICLASS_CLASSIFICATION: CLASSIFICATION_METRICS['accuracy'],
    MULTILABEL_CLASSIFICATION: CLASSIFICATION_METRICS['f1_macro'],
    REGRESSION: REGRESSION_METRICS['r2'],
    MULTIOUTPUT_REGRESSION: REGRESSION_METRICS['r2'],
}
