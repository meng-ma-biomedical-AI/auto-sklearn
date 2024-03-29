import unittest

import numpy as np
import sklearn.metrics

from autosklearn.pipeline.util import _test_regressor, \
    _test_regressor_iterative_fit
from autosklearn.pipeline.constants import SPARSE
from autosklearn.pipeline.components.regression.libsvm_svr import LibSVM_SVR


class BaseRegressionComponentTest(unittest.TestCase):

    res = None

    module = None
    sk_module = None
    # Hyperparameter which is increased by iterative_fit
    step_hyperparameter = None

    # Magic command to not run tests on base class
    __test__ = False

    def test_default_boston(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        for _ in range(2):
            predictions, targets, n_calls = _test_regressor(
                dataset="boston", Regressor=self.module
            )

            if "default_boston_le_ge" in self.res:
                # Special treatment for Gaussian Process Regression
                self.assertLessEqual(
                    sklearn.metrics.r2_score(y_true=targets, y_pred=predictions),
                    self.res["default_boston_le_ge"][0]
                )
                self.assertGreaterEqual(
                    sklearn.metrics.r2_score(y_true=targets, y_pred=predictions),
                    self.res["default_boston_le_ge"][1]
                )
            else:
                score = sklearn.metrics.r2_score(targets, predictions)
                fixture = self.res["default_boston"]
                if score < -1e10:
                    print(f"score = {score}, fixture = {fixture}")
                    score = np.log(-score)
                    fixture = np.log(-fixture)
                self.assertAlmostEqual(
                    fixture,
                    score,
                    places=self.res.get("default_boston_places", 7),
                )

            if self.res.get("boston_n_calls"):
                self.assertEqual(self.res["boston_n_calls"], n_calls)

    def test_default_boston_iterative_fit(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        if not hasattr(self.module, 'iterative_fit'):
            return

        for i in range(2):
            predictions, targets, regressor = \
                _test_regressor_iterative_fit(dataset="boston",
                                              Regressor=self.module)
            score = sklearn.metrics.r2_score(targets, predictions)
            fixture = self.res["default_boston_iterative"]

            if score < -1e10:
                print(f"score = {score}, fixture = {fixture}")
                score = np.log(-score)
                fixture = np.log(-fixture)

            self.assertAlmostEqual(
                fixture,
                score,
                places=self.res.get("default_boston_iterative_places", 7),
            )

            if self.step_hyperparameter is not None:
                self.assertEqual(
                    getattr(regressor.estimator, self.step_hyperparameter['name']),
                    self.res.get("boston_iterative_n_iter", self.step_hyperparameter['value'])
                )

    def test_default_boston_iterative_sparse_fit(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        if not hasattr(self.module, 'iterative_fit'):
            return

        if SPARSE not in self.module.get_properties()["input"]:
            return

        for i in range(2):
            predictions, targets, _ = \
                _test_regressor_iterative_fit(dataset="boston",
                                              Regressor=self.module,
                                              sparse=True)
            self.assertAlmostEqual(self.res["default_boston_iterative_sparse"],
                                   sklearn.metrics.r2_score(targets,
                                                            predictions),
                                   places=self.res.get(
                                           "default_boston_iterative_sparse_places", 7))

    def test_default_boston_sparse(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        if SPARSE not in self.module.get_properties()["input"]:
            return

        for i in range(2):
            predictions, targets, _ = \
                _test_regressor(dataset="boston",
                                Regressor=self.module,
                                sparse=True)
            self.assertAlmostEqual(self.res["default_boston_sparse"],
                                   sklearn.metrics.r2_score(targets,
                                                            predictions),
                                   places=self.res.get(
                                           "default_boston_sparse_places", 7))

    def test_default_diabetes(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        for i in range(2):
            predictions, targets, n_calls = \
                _test_regressor(dataset="diabetes",
                                Regressor=self.module)

            self.assertAlmostEqual(self.res["default_diabetes"],
                                   sklearn.metrics.r2_score(targets,
                                                            predictions),
                                   places=self.res.get(
                                           "default_diabetes_places", 7))

            if self.res.get("diabetes_n_calls"):
                self.assertEqual(self.res["diabetes_n_calls"], n_calls)

    def test_default_diabetes_iterative_fit(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        if not hasattr(self.module, 'iterative_fit'):
            return

        for i in range(2):
            predictions, targets, _ = \
                _test_regressor_iterative_fit(dataset="diabetes",
                                              Regressor=self.module)
            self.assertAlmostEqual(self.res["default_diabetes_iterative"],
                                   sklearn.metrics.r2_score(targets,
                                                            predictions),
                                   places=self.res.get(
                                           "default_diabetes_iterative_places", 7))

    def test_default_diabetes_iterative_sparse_fit(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        if not hasattr(self.module, 'iterative_fit'):
            return

        if SPARSE not in self.module.get_properties()["input"]:
            return

        for i in range(2):
            predictions, targets, regressor = \
                _test_regressor_iterative_fit(dataset="diabetes",
                                              Regressor=self.module,
                                              sparse=True)
            self.assertAlmostEqual(self.res["default_diabetes_iterative_sparse"],
                                   sklearn.metrics.r2_score(targets,
                                                            predictions),
                                   places=self.res.get(
                                           "default_diabetes_iterative_sparse_places", 7))

            if self.step_hyperparameter is not None:
                self.assertEqual(
                    getattr(regressor.estimator, self.step_hyperparameter['name']),
                    self.res.get("diabetes_iterative_n_iter", self.step_hyperparameter['value'])
                )

    def test_default_diabetes_sparse(self):

        if self.__class__ == BaseRegressionComponentTest:
            return

        if SPARSE not in self.module.get_properties()["input"]:
            return

        for i in range(2):
            predictions, targets, _ = \
                _test_regressor(dataset="diabetes",
                                Regressor=self.module,
                                sparse=True)
            self.assertAlmostEqual(self.res["default_diabetes_sparse"],
                                   sklearn.metrics.r2_score(targets,
                                                            predictions),
                                   places=self.res.get(
                                           "default_diabetes_sparse_places", 7))

    def test_module_idempotent(self):
        """ Fitting twice with the same config gives the same model params.

            This is only valid when the random_state passed is an int. If a
            RandomState object is passed then repeated calls to fit will have
            different results. See the section on "Controlling Randomness" in the
            sklearn docs.

            https://scikit-learn.org/0.24/common_pitfalls.html#controlling-randomness
        """
        if self.__class__ == BaseRegressionComponentTest:
            return

        regressor_cls = self.module

        X = np.array([
            [0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5],
            [0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5],
            [0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5],
            [0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5],
        ])
        y = np.array([
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
        ])

        # We ignore certain keys when comparing
        param_keys_ignored = ['base_estimator']

        # We use the default config + sampled ones
        configuration_space = regressor_cls.get_hyperparameter_search_space()

        default = configuration_space.get_default_configuration()
        sampled = [configuration_space.sample_configuration() for _ in range(2)]

        for seed, config in enumerate([default] + sampled):
            model_args = {"random_state": seed, **config}
            regressor = regressor_cls(**model_args)

            # Get the parameters on the first and second fit with config params
            # Also compare their random state
            params_first = regressor.fit(X.copy(), y.copy()).estimator.get_params()
            if hasattr(regressor.estimator, 'random_state'):
                rs_1 = regressor.random_state
                rs_estimator_1 = regressor.estimator.random_state

            params_second = regressor.fit(X.copy(), y.copy()).estimator.get_params()
            if hasattr(regressor.estimator, 'random_state'):
                rs_2 = regressor.random_state
                rs_estimator_2 = regressor.estimator.random_state

            # Remove keys we don't wish to include in the comparison
            for params in [params_first, params_second]:
                for key in param_keys_ignored:
                    if key in params:
                        del params[key]

            # They should have equal parameters
            self.assertEqual(params_first, params_second,
                             f"Failed with model args {model_args}")
            if (
                hasattr(regressor.estimator, 'random_state')
                and not isinstance(regressor, LibSVM_SVR)
            ):
                # sklearn.svm.SVR has it as an attribute but does not use it and
                # defaults it to None, even if a value is passed in
                assert all([
                    seed == random_state
                    for random_state in [rs_1, rs_estimator_1, rs_2, rs_estimator_2]
                ])
