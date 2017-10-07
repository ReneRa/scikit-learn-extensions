"""
This module contains classes to run an experiment across
multiple datasets with various hyperparameters.
"""

# Author: Georgios Douzas <gdouzas@icloud.com>

from os.path import join
from os import listdir
from re import match, sub
from warnings import filterwarnings
from itertools import product
from pickle import dump, load
import pandas as pd
from progressbar import ProgressBar
from sklearn.model_selection import check_cv, GridSearchCV
from sklearn.base import is_classifier
from metriclearn.classification import SCORERS
from .utils import check_datasets, check_random_states, check_estimators, check_param_grids


def read_csv_dir(dirpath):
    "Reads a directory of csv files and returns a dictionary of dataset-name:(X,y) pairs."
    datasets = []
    csv_files = [csv_file for csv_file in listdir(dirpath) if match('^.+\.csv$', csv_file)]
    for csv_file in csv_files:
        dataset = pd.read_csv(join(dirpath, csv_file))
        X, y = dataset.iloc[:, :-1], dataset.iloc[:, -1]
        dataset_name = sub(".csv", "", csv_file)
        datasets.append((dataset_name, (X, y)))
    return datasets

def load_experiment(filename):
    """Loads a saved experiment object."""
    loaded_obj = load(open(filename, 'rb'))
    if not isinstance(loaded_obj, BaseExperiment):
        raise TypeError("File {} is not a BinaryExperiment instance.")
    return loaded_obj

class BaseExperiment:
    """Base class for execution of various machine learning experiments.

    Warning: This class should not be used directly. Use the derive classes
    instead.
    """

    def __init__(self, scoring, cv, n_jobs):
        self.scoring = scoring
        self.cv = cv
        self.n_jobs = n_jobs

    def save(self, filename, pickle_datasets=False):
        """Pickles the experiment object."""
        if not pickle_datasets:
            if hasattr(self, 'datasets'):
                delattr(self, 'datasets')
        dump(self, open(filename, 'wb'))


class ExtendedExperiment(BaseExperiment):
    """Class for comparison of a various transformations/estimators 
    pipelines across multiple datasets.

    Parameters
    ----------
    datasets : list of (dataset name, (X, y)) tuples
        The dataset name is a string and (X, y) are tuples of input data and
        target values.
    estimators : list of (estimator name, estimator, param_grid) tuples
        Each estimator is a single estimator or an estimator pipeline.
    scoring : string, callable, list/tuple, dict or None, default: None
        A single string (see :ref:`scoring_parameter`) or a callable
        to evaluate the predictions on the test set. For evaluating multiple 
        metrics, either give a list of (unique) strings or a dict 
        with names as keys and callables as values.
    cv : int, cross-validation generator or an iterable, optional
        Determines the cross-validation splitting strategy.
        Possible inputs for cv are:
        - None, to use the default 3-fold cross validation.
        - integer, to specify the number of folds in a `(Stratified)KFold`.
        - An object to be used as a cross-validation generator.
        - An iterable yielding train, test splits.
    experiment_repetitions : int, (default=5)
        The number of experiment repetitions.
    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.
    n_jobs : int, (default=1)
        The number of CPUs to use to do the computation. -1 means ‘all CPUs’.
    """

    def __init__(self,
                 datasets,
                 estimators,
                 scoring=['roc_auc', 'f1', 'geometric_mean_score'],
                 cv=None,
                 experiment_repetitions=5,
                 random_state=None,
                 n_jobs=1):
        super().__init__(scoring, cv, n_jobs)
        self.estimators = estimators
        self.datasets = datasets
        self.experiment_repetitions = experiment_repetitions
        self.random_state = random_state

    def run(self, hide_warnings=True):
        """Runs the experimental procedure and calculates the cross validation
        scores for each dataset, pipeline and hyperparameters."""

        # Remove warnings
        if hide_warnings:
            filterwarnings('ignore')
        else:
            filterwarnings('default')

        if not hasattr(self, 'datasets'):
            return
        datasets = check_datasets(self.datasets)
        self.estimators_ = check_estimators(self.estimators)
        self.param_grids_ = check_param_grids(self.estimators)
        self.random_states_ = check_random_states(self.random_state, self.experiment_repetitions)

        # Initialize progress bar
        progress_bar = ProgressBar(redirect_stdout=False, max_value=len(self.random_states_) * len(datasets) * len(self.estimators_))
        iterations = 0

        # Create all possible combination of experimental configurations
        combinations = product(self.random_states_, datasets, zip(self.estimators_, self.param_grids_))

        # Run the experiment
        self.results_ = []
        for random_state, (dataset_name, (X, y)), (estimator, param_grid) in combinations:
            cv = check_cv(self.cv, y, is_classifier(estimator))
            cv.shuffle = True
            cv.random_state = random_state
            gscv = GridSearchCV(estimator, param_grid, self.scoring, cv=cv, refit=False, n_jobs=self.n_jobs)
            gscv.fit(X, y)
            self.results_.append((dataset_name, gscv))
            iterations += 1
            progress_bar.update(iterations)


class ResamplingExperiment(BaseExperiment):
    """Class for comparison of resamplers across multiple datasets.

    Parameters
    ----------
    datasets : list of (dataset name, (X, y)) tuples
        The dataset name is a string and (X, y) are tuples of input data and
        target values.
    classifiers : list of (classifier name, classifier, param_grid) tuples
        The list of classifiers used during the experiment.
    resamplers : list of (resampler name, resampler, param_grid) tuples
        The list of resamplers used during the experiment.
    scoring : string, callable, list/tuple, dict or None, default: None
        A single string (see :ref:`scoring_parameter`) or a callable
        to evaluate the predictions on the test set. For evaluating multiple 
        metrics, either give a list of (unique) strings or a dict 
        with names as keys and callables as values.
    cv : int, cross-validation generator or an iterable, optional
        Determines the cross-validation splitting strategy.
        Possible inputs for cv are:
        - None, to use the default 3-fold cross validation.
        - integer, to specify the number of folds in a `(Stratified)KFold`.
        - An object to be used as a cross-validation generator.
        - An iterable yielding train, test splits.
    experiment_repetitions : int, (default=5)
        The number of experiment repetitions.
    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.
    n_jobs : int, (default=1)
        The number of CPUs to use to do the computation. -1 means ‘all CPUs’.
    """

    def __init__(self,
                 datasets,
                 classifiers,
                 resamplers,
                 scoring=['roc_auc', 'f1', 'geometric_mean_score'],
                 cv=None,
                 experiment_repetitions=5,
                 random_state=None,
                 n_jobs=1):
        self.datasets = datasets
        self.classifiers = classifiers
        self.resamplers = resamplers
        self.scoring = scoring
        self.cv = cv
        self.experiment_repetitions = experiment_repetitions
        self.random_state = random_state
        self.n_jobs = n_jobs

    def run(self, hide_warnings=True):
        """Runs the experimental procedure and calculates the cross validation
        scores for each dataset, pipeline and hyperparameters."""

        # Remove warnings
        if hide_warnings:
            filterwarnings('ignore')
        else:
            filterwarnings('default')

        # Initialize experiment parameters
        if not hasattr(self, 'datasets'):
            return
        datasets = check_datasets(self.datasets)
        estimators = [[resampler, classifier] if resampler[1] is not None else [classifier] for (resampler, classifier) in product(self.resamplers, self.classifiers)]
        self.estimators = estimators
        self.estimators_ = check_estimators(estimators)
        self.param_grids_ = check_param_grids(estimators, 'resampling')
        self.random_states_ = check_random_states(self.random_state, self.experiment_repetitions)

        # Initialize progress bar
        progress_bar = ProgressBar(redirect_stdout=False, max_value=len(self.random_states_) * len(datasets) * len(self.estimators_))
        iterations = 0

        # Create all possible combination of experimental configurations
        combinations = product(self.random_states_, datasets, zip(self.estimators_, self.param_grids_))

        # Run the experiment
        self.results_ = []
        for random_state, (dataset_name, (X, y)), (estimator, param_grid) in combinations:
            cv = check_cv(self.cv, y, is_classifier(estimator))
            cv.shuffle = True
            cv.random_state = random_state
            gscv = GridSearchCV(estimator, param_grid, self.scoring, cv=cv, refit=False, n_jobs=self.n_jobs)
            gscv.fit(X, y)
            self.results_.append((dataset_name, gscv))
            iterations += 1
            progress_bar.update(iterations)


class KaggleCompetition(BaseExperiment):
    """Class for comparison of a various transformations/estimators 
    pipelines across multiple datasets.

    Parameters
    ----------
    datasets : list of (dataset name, (X, y)) tuples
        The dataset name is a string and (X, y) are tuples of input data and
        target values.
    estimators : list of (estimator name, estimator, param_grid) tuples
        Each estimator is a single estimator or an estimator pipeline.
    scoring : string, callable, list/tuple, dict or None, default: None
        A single string (see :ref:`scoring_parameter`) or a callable
        to evaluate the predictions on the test set. For evaluating multiple 
        metrics, either give a list of (unique) strings or a dict 
        with names as keys and callables as values.
    cv : int, cross-validation generator or an iterable, optional
        Determines the cross-validation splitting strategy.
        Possible inputs for cv are:
        - None, to use the default 3-fold cross validation.
        - integer, to specify the number of folds in a `(Stratified)KFold`.
        - An object to be used as a cross-validation generator.
        - An iterable yielding train, test splits.
    experiment_repetitions : int, (default=5)
        The number of experiment repetitions.
    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.
    n_jobs : int, (default=1)
        The number of CPUs to use to do the computation. -1 means ‘all CPUs’.
    """

    def __init__(self,
                 datasets,
                 estimators,
                 scoring=['roc_auc', 'f1', 'geometric_mean_score'],
                 cv=None,
                 experiment_repetitions=5,
                 random_state=None,
                 n_jobs=1):
        self.datasets = datasets
        self.estimators = estimators
        self.scoring = scoring
        self.cv = cv
        self.experiment_repetitions = experiment_repetitions
        self.random_state = random_state
        self.n_jobs = n_jobs

    def run(self, hide_warnings=True):
        """Runs the experimental procedure and calculates the cross validation
        scores for each dataset, pipeline and hyperparameters."""

        # Remove warnings
        if hide_warnings:
            filterwarnings('ignore')
        else:
            filterwarnings('default')

        # Initialize experiment parameters
        if not hasattr(self, 'datasets'):
            return
        datasets = check_datasets(self.datasets)
        self.estimators_ = check_estimators(self.estimators)
        self.param_grids_ = check_param_grids(self.estimators)
        self.random_states_ = check_random_states(self.random_state, self.experiment_repetitions)

        # Initialize progress bar
        progress_bar = ProgressBar(redirect_stdout=False, max_value=len(self.random_states_) * len(datasets) * len(self.estimators_))
        iterations = 0

        # Create all possible combination of experimental configurations
        combinations = product(self.random_states_, datasets, zip(self.estimators_, self.param_grids_))

        # Run the experiment
        self.results_ = []
        for random_state, (dataset_name, (X, y)), (estimator, param_grid) in combinations:
            cv = check_cv(self.cv, y, is_classifier(estimator))
            cv.shuffle = True
            cv.random_state = random_state
            gscv = GridSearchCV(estimator, param_grid, self.scoring, cv=cv, refit=False, n_jobs=self.n_jobs)
            gscv.fit(X, y)
            self.results_.append((dataset_name, gscv))
            iterations += 1
            progress_bar.update(iterations)

    def save(self, filename, pickle_datasets=False):
        """Pickles the experiment object."""
        if not pickle_datasets:
            if hasattr(self, 'datasets'):
                delattr(self, 'datasets')
        dump(self, open(filename, 'wb'))