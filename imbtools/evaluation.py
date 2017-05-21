import pandas as pd
from os import listdir, chdir
from re import match, sub
from sklearn.model_selection import StratifiedKFold
from imblearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score
from sklearn.metrics import make_scorer


def count_elements(elements):
    """Returns a list with modified elements by a count index."""
    elements_map = {}
    elements_modified = []
    for element in elements:
        if element in elements_map.keys():
            elements_map[element] += 1
            elements_modified.append(element + str(elements_map[element]))
        else:
            elements_map[element] = 1
            elements_modified.append(element)
    return elements_modified


class BinaryExperiment:
    """Class for comparison of oversampling algorithms performance 
    on imbalanced binary classification problems."""

    def __init__(self, 
        oversampling_methods, 
        classifiers, 
        metrics, 
        datasets,
        n_splits=3, 
        experiment_repetitions=5, 
        random_state=None):
        self.oversampling_methods = oversampling_methods
        self.classifiers = classifiers
        self.metrics = metrics
        self.datasets = datasets
        self.n_splits = n_splits
        self.experiment_repetitions = experiment_repetitions
        self.random_state = random_state

    def _initialize_parameters(self):
        """Private method that initializes the experiment's parameters."""
        self.scorers_ = [make_scorer(metric) for metric in self.metrics]
        if isinstance(self.datasets, str):
            chdir(self.datasets)
            self.datasets = {}
            csv_files = [csv_file for csv_file in listdir() if match('^.+\.csv$', csv_file)]
            for csv_file in csv_files:
                dataset = pd.read_csv(csv_file)
                X, y = dataset.iloc[:, :-1], dataset.iloc[:, -1]
                dataset_name = sub(".csv", "", csv_file)
                self.datasets[dataset_name] = (X, y)
        self.random_states_ = [self.random_state * index for index in range(self.experiment_repetitions)] if self.random_state is not None else [None] * self.experiment_repetitions
        self.cv_scores_ = []
        self.classifiers_names_ = count_elements([classifier.__class__.__name__ for classifier in self.classifiers])
        self.oversampling_methods_names_ = count_elements([oversampling_method.__class__.__name__ for oversampling_method in self.oversampling_methods])
        self.metrics_names_ = [metric.__name__ for metric in self.metrics]
        self.datasets_names_ = self.datasets.keys()
        
    def run(self):
        """Runs the experimental procedure and calculates the cross validation 
        scores for each classifier, oversampling method, datasets and metric."""
        self._initialize_parameters()
        for experiment_ind, random_state in enumerate(self.random_states_):
            cv = StratifiedKFold(n_splits=self.n_splits, random_state=random_state)
            for clf_ind, clf in enumerate(self.classifiers):
                clf.set_params(random_state=random_state)
                for oversampling_method_ind, oversampling_method in enumerate(self.oversampling_methods):
                    oversampling_method.set_params(random_state=random_state)
                    for scorer_ind, scorer in enumerate(self.scorers_):
                        for dataset_ind, (X, y) in enumerate(self.datasets.values()):
                            if oversampling_method is not None:
                                clf = make_pipeline(oversampling_method, clf)
                            clf_name = self.classifiers_names_[clf_ind]
                            om_name = self.oversampling_methods_names_[oversampling_method_ind]
                            metric_name = self.metrics_names_[scorer_ind]
                            dataset_name = list(self.datasets_names_)[dataset_ind]
                            cv_score = cross_val_score(clf, X, y, cv=cv, scoring=scorer).mean()
                            msg = 'Experiment: {}\nClassifier: {}\nOversampling method: {}\nMetric: {}\nDataset: {}\nCV score: {}\n\n'
                            print(msg.format(experiment_ind + 1, clf_name, om_name, metric_name, dataset_name, cv_score))
                            self.cv_scores_.append(cv_score)

    def get_mean_results():
        pass

    def get_std_results():
        pass

    def get_ranking_results():
        pass

    def get_friedman_test_results():
        pass
