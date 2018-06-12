import nibabel as nib
import numpy as np
import pandas as pd
import scipy.stats as sps
import multiprocessing as mp
from os import path
from joblib import Parallel, delayed

try:
	FileNotFoundError
except NameError:
	FileNotFoundError = IOError

def significant_signal(data_path,
	substitution={},
	mask_path='',
	):
	"""Return the mean and median inverse logarithm of a p-value map.

	Parameters
	----------

	data_path : str
		Path to a p-value map in NIfTI format.
	mask_path : str
		Path to a region of interest map in NIfTI format.
		THIS IS ALMOST ALWAYS REQUIRED, as NIfTI statistic images populate the whole 3D circumscribed space around your structure of interest,
		and commonly assign null values to the background.
		In an inverse logarithm computation, null corresponds to infinity, which can considerably bias the evaluation.
	substitution : dict
		Dictionary whose keys are format identifiers present in `data_path` and whose values are strings.

	Returns
	-------

	mean : float
	median : float
	"""

	if substitution:
		data_path = data_path.format(**substitution)
	data_path = path.abspath(path.expanduser(data_path))
	try:
		data = nib.load(data_path).get_data()
	except FileNotFoundError:
		return float('NaN'), float('NaN')
	if mask_path:
		mask_path = path.abspath(path.expanduser(mask_path))
		mask = nib.load(mask_path).get_data()
		mask = (mask < 0.5).astype(int)
		data = np.ma.masked_array(data, mask=mask)
		data = data[~np.isnan(data)]
	nonzero = data[np.nonzero(data)]
	data_min = np.min(nonzero)*0.99
	data[data == 0] = data_min
	data = -np.log10(data)
	# We use np.ma.median() because life is complicated:
	# https://github.com/numpy/numpy/issues/7330
	median = np.ma.median(data, axis=None)
	mean = np.mean(data)

	return mean, median

def iter_significant_signal(file_template, substitutions,
	mask_path='',
	save_as='',
	):
	"""
	Create a `pandas.DataFrame` (optionally savable as `.csv`), containing the means and medians of a number of p-value maps specified by a file template supporting substitution and a substitution list of dictionaries.
	This function is an iteration wrapper of `samri.report.snr.significant_signal()` using the SAMRI file_template/substitution model.

	Parameters
	----------

	file_template : str
		A formattable string containing as format fields keys present in the dictionaries passed to the `substitutions` variable.
	substitutions : list of dicts
		A list of dictionaries countaining formatting strings as keys and strings as values.
	mask_path : str, optional
		Path to a mask in the same coordinate space as the p-value maps.
	save_as : str, optional
		Path to which to save the Pandas DataFrame.

	Returns
	-------

	pandas.DataFrame
		Pandas DataFrame object containing a row for each analyzed file and columns named 'Mean', 'Median', and (provided the respective key is present in the `sustitutions` variable) 'subject', 'session', 'task', and 'acquisition'.
	"""

	n_jobs = mp.cpu_count()-2
	iter_data = Parallel(n_jobs=n_jobs, verbose=0, backend="threading")(map(delayed(significant_signal),
		[file_template]*len(substitutions),
		substitutions,
		[mask_path]*len(substitutions),
		))

	df_items = [
		('Mean', [i[0] for i in iter_data]),
		('Median', [i[1] for i in iter_data]),
		]
	df = pd.DataFrame.from_items(df_items)
	for field in ['subject','session','task','acquisition']:
		try:
			df[field] = [i[field] for i in substitutions]
		except KeyError:
			pass
	if save_as:
		save_as = path.abspath(path.expanduser(save_as))
		if save_as.lower().endswith('.csv'):
			df.to_csv(save_as)
		else:
			raise ValueError("Please specify an output path ending in any one of "+",".join((".csv",))+".")
	return df

def base_metrics(file_path,
	substitution={},
	):
	"""Return base metrics (mean, median, mode, standard deviation) at each 4th dimension point of a 4D NIfTI file.

	Parameters
	----------

	file_path : str
		A string giving the path to the NIfTI file to be analyzed.
		This string may contain format fields present as keys in the `substitution` dictionary.
	substitution : dict, optional
		A dictionary containing formatting strings as keys and strings as values.

	Returns
	-------

	pandas.DataFrame
		Pandas DataFrame object containing a row for each analyzed file and columns named 'Mean', 'Median', 'Mode', and 'Standard Deviation', and (provided the respective key is present in the `sustitution` variable) 'subject', 'session', 'task', and 'acquisition'.
	"""


	if substitution:
		file_path = file_path.format(**substitution)
	file_path = path.abspath(path.expanduser(file_path))
	file_path = path.abspath(path.expanduser(file_path))
	data = nib.load(file_path).get_data()
	data = data.T

	stds = []
	means = []
	medians = []
	modes = []
	for i in data:
		i_std = np.std(i)
		stds.append(i_std)
		i_mean = np.mean(i)
		means.append(i_mean)
		i_median = np.median(i)
		medians.append(i_median)
		i_mode,_ = sps.mode(i, axis=None)
		modes.append(i_mode[0])

	df_items = [
		('Mean', means),
		('Median', medians),
		('Mode', modes),
		('Standard Deviation', stds),
		]
	df = pd.DataFrame.from_items(df_items)
	for field in ['subject','session','task','acquisition']:
		try:
			df[field] = substitution[field]
		except KeyError:
			pass
	return df

def iter_base_metrics(file_template, substitutions,
	save_as='',
	):
	"""
	Create a `pandas.DataFrame` (optionally savable as `.csv`), containing base metrics (mean, median, mode, standard deviation) at each 4th dimension point of a 4D NIfTI file.
	This function is an iteration wrapper of `samri.report.snr.base_metrics()` using the SAMRI file_template/substitution model.

	Parameters
	----------

	file_template : str
		A formattable string containing as format fields keys present in the dictionaries passed to the `substitutions` variable.
	substitutions : list of dicts
		A list of dictionaries countaining formatting strings as keys and strings as values.
	save_as : str, optional
		Path to which to save the Pandas DataFrame.

	Returns
	-------

	pandas.DataFrame
		Pandas DataFrame object containing a row for each analyzed file and columns named 'Mean', 'Median', 'Mode', and 'Standard Deviation', and (provided the respective key is present in the `sustitutions` variable) 'subject', 'session', 'task', and 'acquisition'.
	"""

	n_jobs = mp.cpu_count()-2
	base_metrics_data = Parallel(n_jobs=n_jobs, verbose=0, backend="threading")(map(delayed(base_metrics),
		[file_template]*len(substitutions),
		substitutions,
		))

	df = pd.concat(base_metrics_data)

	if save_as:
		save_as = path.abspath(path.expanduser(save_as))
		if save_as.lower().endswith('.csv'):
			df.to_csv(save_as)
		else:
			raise ValueError("Please specify an output path ending in any one of "+",".join((".csv",))+".")
	return df
