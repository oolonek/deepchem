"""
Utility functions to evaluate models on datasets.
"""
__author__ = "Bharath Ramsundar"
__copyright__ = "Copyright 2015, Stanford University"
__license__ = "LGPL"

def model_predictions(test_set, model, n_targets, n_descriptors=0,
    add_descriptors=False, modeltype="sklearn"):
  """Obtains predictions of provided model on test_set.

  Returns a list of per-task predictions.

  TODO(rbharath): This function uses n_descriptors, n_targets instead of
  task_transforms, desc_transforms like everything else.

  Parameters
  ----------
  test_set: dict 
    A dictionary of type produced by load_datasets. Contains the test-set.
  model: model.
    A trained scikit-learn or keras model.
  n_targets: int
    Number of output targets
  n_descriptors: int
    Number of output descriptors
  modeltype: string
    Either sklearn, keras, or keras_multitask
  add_descriptors: bool
    Add descriptor prediction as extra task.
  """
  # Extract features for test set and make preds
  X, _, _ = dataset_to_numpy(test_set)
  if add_descriptors:
    n_outputs = n_targets + n_descriptors
  else:
    n_outputs = n_targets
  if modeltype == "sklearn":
    ypreds = model.predict_proba(X)
  elif modeltype == "keras":
    ypreds = model.predict(X)
  elif modeltype == "keras_multitask":
    predictions = model.predict({"input": X})
    ypreds = []
    for index in range(n_outputs):
      ypreds.append(predictions["task%d" % index])
  else:
    raise ValueError("Improper modeltype.")
  # Handle the edge case for singletask. 
  if type(ypreds) != list:
    ypreds = [ypreds]
  return ypreds
  
def eval_model(test_set, model, task_types, desc_transforms={}, modeltype="sklearn",
    add_descriptors=False):
  """Evaluates the provided model on the test-set.

  Returns a dict which maps target-names to pairs of np.ndarrays (ytrue,
  yscore) of true labels vs. predict

  TODO(rbharath): This function is too complex. Refactor and simplify.
  TODO(rbharath): The handling of add_descriptors for semi-supervised learning
  is horrible. Refactor.

  Parameters
  ----------
  test_set: dict 
    A dictionary of type produced by load_datasets. Contains the test-set.
  model: model.
    A trained scikit-learn or keras model.
  task_types: dict 
    dict mapping target names to output type. Each output type must be either
    "classification" or "regression".
  desc_transforms: dict
    dict mapping descriptor number to transform. Each transform must be
    either None, "log", "normalize", or "log-normalize"
  modeltype: string
    Either sklearn, keras, or keras_multitask
  add_descriptors: bool
    Add descriptor prediction as extra task.
  """
  sorted_targets = sorted(task_types.keys())
  if add_descriptors:
    sorted_descriptors = sorted(desc_transforms.keys())
    endpoints = sorted_targets + sorted_descriptors
    local_task_types = task_types.copy()
    for desc in desc_transforms:
      local_task_types[desc] = "regression"
  else:
    local_task_types = task_types.copy()
    endpoints = sorted_targets
  ypreds = model_predictions(test_set, model, len(sorted_targets),
      n_descriptors=len(desc_transforms), modeltype=modeltype,
      add_descriptors=add_descriptors)
  results = {}
  for target in endpoints:
    results[target] = ([], [])  # (ytrue, yscore)
  # Iterate through test set data points.
  sorted_smiles = sorted(test_set.keys())
  for index, smiles in enumerate(sorted_smiles):
    datapoint = test_set[smiles]
    labels = datapoint["labels"]
    for t_ind, target in enumerate(endpoints):
      task_type = local_task_types[target]
      if target in sorted_targets and labels[target] == -1:
        continue
      else:
        ytrue, yscore = results[target]
        if task_type == "classification":
          if labels[target] == 0:
            ytrue.append(0)
          elif labels[target] == 1:
            ytrue.append(1)
          else:
            raise ValueError("Labels must be 0/1.")
        elif target in sorted_targets and task_type == "regression":
          ytrue.append(labels[target])
        elif target not in sorted_targets and task_type == "regression":
          descriptors = datapoint["descriptors"]
          # The "target" for descriptors is simply the index in the
          # descriptor vector.
          ytrue.append(descriptors[int(target)])
        else:
          raise ValueError("task_type must be classification or regression.")
        yscore.append(ypreds[t_ind][index])
  for target in endpoints:
    ytrue, yscore = results[target]
    results[target] = (np.array(ytrue), np.array(yscore))
  return results

def compute_roc_auc_scores(results, task_types):
  """Transforms the results dict into roc-auc-scores and prints scores.

  Parameters
  ----------
  results: dict
    A dictionary of type produced by eval_model which maps target-names to
    pairs of lists (ytrue, yscore).
  task_types: dict 
    dict mapping target names to output type. Each output type must be either
    "classification" or "regression".
  """
  scores = {}
  for target in results:
    if task_types[target] != "classification":
      continue
    ytrue, yscore = results[target]
    sample_weights = labels_to_weights(ytrue)
    print "np.shape(ytrue)"
    print np.shape(ytrue)
    print "np.shape(yscore)"
    print np.shape(yscore)
    score = roc_auc_score(ytrue, yscore[:,1], sample_weight=sample_weights)
    #score = roc_auc_score(ytrue, yscore, sample_weight=sample_weights)
    print "Target %s: AUC %f" % (target, score)
    scores[target] = score
  return scores

def compute_r2_scores(results, task_types):
  """Transforms the results dict into R^2 values and prints them.

  Parameters
  ----------
  results: dict
    A dictionary of type produced by eval_regression_model which maps target-names to
    pairs of lists (ytrue, yscore).
  task_types: dict 
    dict mapping target names to output type. Each output type must be either
    "classification" or "regression".
  """
  scores = {}
  for target in results:
    if task_types[target] != "regression":
      continue
    ytrue, yscore = results[target]
    score = r2_score(ytrue, yscore)
    print "Target %s: R^2 %f" % (target, score)
    scores[target] = score
  return scores

def compute_rms_scores(results, task_types):
  """Transforms the results dict into RMS values and prints them.

  Parameters
  ----------
  results: dict
    A dictionary of type produced by eval_regression_model which maps target-names to
    pairs of lists (ytrue, yscore).
  task_types: dict 
    dict mapping target names to output type. Each output type must be either
    "classification" or "regression".
  """
  scores = {}
  for target in results:
    if task_types[target] != "regression":
      continue
    ytrue, yscore = results[target]
    rms = np.sqrt(mean_squared_error(ytrue, yscore))
    print "Target %s: RMS %f" % (target, rms)
    scores[target] = rms 
  return scores