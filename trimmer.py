"""
A set of scripts for cutting files with spectral lines
and drawing them in a synthetic spectrum
"""
import os
import datetime
import numpy as np
import logging
import shutil
import re
from file_processor import synt_grab, obs_grab


def create_window_linelist(seg_begins: np.ndarray[float], seg_ends: np.ndarray[float], old_path_name: str,
                           new_path_name: str, molecules_flag: bool, lbl=False, do_hydrogen=True):
    """
    Creates a new linelist from the old one, but only with the lines that are within the given segments. If lbl is True,
    then the linelist is created for each segment separately. If lbl is False, then the linelist is created for all
    segments together in the same file. If do_hydrogen is False, then the linelist is not created for hydrogen.
    :param seg_begins: Array of segment beginnings
    :param seg_ends: Array of segment ends
    :param old_path_name: Path to the folder with the old linelists
    :param new_path_name: Path to the folder where the new linelists will be saved
    :param molecules_flag: If True, then the molecules are included in the new linelists.
    :param lbl: If True, then the linelist is created for each segment separately. If False, then the linelist is created
    for all segments together in the same folder. /new_path_name/0/*
    :param do_hydrogen: If False, then the linelist is not created for hydrogen.
    """
    # get all files in directory
    line_list_files: list = [entry.path for entry in os.scandir(old_path_name) if entry.is_file()]

    # go through all files in line_list_files and if any ends with .DS_Store, remove it
    for line_list_file in line_list_files:
        if line_list_file.endswith(".DS_Store"):
            # print warning that DS_Store file is removed
            logging.debug(f"LINELIST WARNING! File {line_list_file} is a .DS_Store file and will be removed")
            line_list_files.remove(line_list_file)

    # convert to numpy arrays in case they are not
    segment_to_use_begins: np.ndarray = np.asarray(seg_begins)
    segment_to_use_ends: np.ndarray = np.asarray(seg_ends)

    # sort the segments
    segment_index_order: np.ndarray = np.argsort(segment_to_use_begins)
    segment_to_use_begins: np.ndarray = segment_to_use_begins[segment_index_order]
    segment_to_use_ends: np.ndarray = segment_to_use_ends[segment_index_order]
    segment_min_wavelength: float = np.min(segment_to_use_begins)
    segment_max_wavelength: float = np.max(segment_to_use_ends)

    if not lbl:
        # if lbl is False, then we create the linelist for all segments together in the same folder
        os.makedirs(os.path.join(f"{new_path_name}", "0", ''))
    else:
        # if lbl is True, then we create the folder for each segment separately
        for seg_idx in range(len(seg_begins)):
            new_path_name_one_seg: str = os.path.join(f"{new_path_name}", f"{seg_idx}", '')
            os.makedirs(new_path_name_one_seg)

    # go through all files in the old linelist folder
    for line_list_number, line_list_file in enumerate(line_list_files):
        with open(line_list_file) as fp:
            # so that we dont read full file if we are not sure that we use it (if it is a molecule)
            try:
                first_line: str = fp.readline()
            except UnicodeDecodeError:
                print(f"LINELIST WARNING! File {line_list_file} is not a valid linelist file")
                continue
            # check if line is empty
            if not first_line:
                print(f"LINELIST WARNING! File {line_list_file} is empty")
                continue
            fields = first_line.strip().split()
            sep = '.'
            element = fields[0] + fields[1]
            elements = element.split(sep, 1)[0]
            # opens each file, reads first row, if it is long enough then it is molecule. If fitting molecules, then
            # keep it, otherwise ignore molecules
            if len(elements) > 3 and molecules_flag or len(elements) <= 3:
                # keep track of the lines to write
                lines_to_write_indices: dict = {}
                if element == "'01.000000'" and do_hydrogen:
                    # if it is hydrogen, then we do not read the whole file
                    # instead we just copy the file
                    # use shutil.copyfile instead of open and write
                    if not lbl:
                        # if not lbl, we just copy the file once
                        new_linelist_name: str = os.path.join(f"{new_path_name}", "0",
                                                              f"linelist-{line_list_number}.bsyn")
                        shutil.copyfile(line_list_file, new_linelist_name)
                    else:
                        # if lbl, we copy the file for each segment
                        for seg_index in range(len(seg_begins)):
                            new_linelist_name: str = os.path.join(f"{new_path_name}", f"{seg_index}",
                                                                  f"linelist-{line_list_number}.bsyn")
                            shutil.copyfile(line_list_file, new_linelist_name)
                elif element != '01.000000':
                    # if it is not hydrogen, and we want to read it (e.g. molecules_flag is True)
                    # now read the whole file
                    lines_file: list[str] = fp.readlines()
                    # keep track of the lines read
                    line_number_read_file: int = 0
                    # since we read the first line already, we add 1 to the total number of lines in the file
                    total_lines_in_file: int = len(lines_file) + 1
                    # keep track of the first line read
                    line: str = first_line
                    first_line_read: bool = True
                    while line_number_read_file + 1 < total_lines_in_file:
                        # go through all lines.
                        # this while loop, loops through all elements
                        # so each iteration is a specific element
                        if not first_line_read:
                            # if it is not the first line, read the next line
                            line: str = lines_file[line_number_read_file]
                            line_number_read_file += 1
                        else:
                            # if it is the first line, then we already read it
                            # not inserting the first line into the lines_file, because that is expensive
                            first_line_read: bool = False
                        # first line is e.g. '   3.000            '    1	13
                        # so element, ion, and number of lines
                        fields: list[str] = line.strip().split()

                        if len(fields[0]) > 1:  # save the first two lines of an element for the future
                            elem_line_1_to_save: str = f"{fields[0]} {fields[1]}  {fields[2]}"  # first line of the element
                            number_of_lines_element: int = int(fields[3])
                        else:
                            elem_line_1_to_save: str = f"{fields[0]}   {fields[1]}            {fields[2]}    {fields[3]}"
                            number_of_lines_element: int = int(fields[4])
                        # second line is e.g. 'Li I    LTE'
                        # so element, ion, and LTE or NLTE
                        elem_line_2_to_save: str = lines_file[line_number_read_file]
                        line_number_read_file += 1

                        # now we are reading the element's wavelength and stuff

                        # to not redo strip/split every time, save wavelength for the future here
                        element_wavelength_dictionary = {}

                        # wavelength minimum and maximum for the element (assume sorted)
                        wavelength_minimum_element: float = get_wavelength_from_array(lines_file, element_wavelength_dictionary, 0, line_number_read_file)
                        wavelength_maximum_element: float = get_wavelength_from_array(lines_file, element_wavelength_dictionary, number_of_lines_element - 1, line_number_read_file)

                        # check that ANY wavelengths are within the range at all
                        if not (wavelength_maximum_element < segment_min_wavelength or wavelength_minimum_element > segment_max_wavelength):
                            # go through all segments to figure out which lines are within the segment for this element
                            for seg_index, (seg_begin, seg_end) in enumerate(zip(segment_to_use_begins, segment_to_use_ends)):
                                # find the index of the first line within the segment
                                # i.e. the first line with wavelength >= seg_begin
                                index_seg_start = binary_find_left_segment_index(lines_file, element_wavelength_dictionary,
                                                                                 0, number_of_lines_element,
                                                                                 line_number_read_file, seg_begin)
                                wavelength_current_line: float = element_wavelength_dictionary[index_seg_start]
                                if seg_begin <= wavelength_current_line <= seg_end:
                                    # if the first line is within the segment, then we find the last line within the segment
                                    index_seg_end = binary_find_right_segment_index(lines_file, element_wavelength_dictionary,
                                                                                    index_seg_start, number_of_lines_element,
                                                                                    line_number_read_file, seg_end)
                                    # now we know that element's wavelengths from index_seg_start to index_seg_end are within the segment
                                    if lbl:
                                        # if lbl is True, then we save the lines to write for each segment separately
                                        seg_current_index = seg_index
                                    else:
                                        # if lbl is False, then we save the lines to write for all segments together
                                        seg_current_index = 0
                                    if seg_current_index not in lines_to_write_indices:
                                        # to keep track of all segments if lbl is False, we need to create list with indices of lines to write
                                        lines_to_write_indices[seg_current_index] = []
                                    # add the indices of the lines to write using slice.
                                    # they will be written to the new linelist later for lines using
                                    # lines_file[index_start:index_end]. Thus we add (index_start, index_end + 1)
                                    # (otherwise last line not written) and with offset of line_number_read_file
                                    lines_to_write_indices[seg_current_index].append((index_seg_start + line_number_read_file, index_seg_end + line_number_read_file + 1))
                        # update the line number read in the file
                        line_number_read_file: int = number_of_lines_element + line_number_read_file
                        # if we have lines to write, then we write them
                        if lines_to_write_indices:
                            write_lines(lines_to_write_indices, lines_file, elem_line_1_to_save, elem_line_2_to_save,
                                        new_path_name, line_list_number)
                            # clear the dictionary instead of creating new one
                            lines_to_write_indices.clear()

def binary_search_lower_bound(array_to_search: list[str], dict_array_values: dict, low: int, high: int,
                              element_to_search: float) -> int:
    """
    OLD FUNCTION, just left here as a reference/backwards compatibility
	Gives out the upper index where the value is located between the ranges. For example, given array [12, 20, 32, 40, 52]
	Value search: 5, result: 0
	Value search: 13, result: 1
	Value search: 20, result: 1
	Value search: 21, result: 2
	Value search: 51 or 52 or 53, result: 4
	:param array_to_search:
	:param dict_array_values:
	:param low:
	:param high:
	:param element_to_search:
	:return:
	"""
    if element_to_search >= float(array_to_search[-1].strip().split()[0]):
        return min(high, len(array_to_search) - 1)
    while low < high:
        middle: int = low + (high - low) // 2

        if middle not in dict_array_values:
            dict_array_values[middle] = float(array_to_search[middle].strip().split()[0])
        array_element_value: float = dict_array_values[middle]

        if array_element_value < element_to_search:
            low: int = middle + 1
        else:
            high: int = middle
    return low

def get_wavelength_from_array(array_to_search: list[str], dict_array_values: dict, index_to_search: int, offset_idx: int):
    """
    Get the wavelength from the array. If it is not in the dictionary, then add it to the dictionary.
    That is done because converting the string to float is expensive, so we do it only once.
    :param array_to_search: Array to search with all lines from the file, where first element is usually the wavelength
    :param dict_array_values: Dictionary to keep track of the wavelengths
    :param index_to_search: Index to search
    :param offset_idx: Offset index to add to the index to search in the array
    :return: Wavelength from the array
    """
    if index_to_search not in dict_array_values:
        dict_array_values[index_to_search] = float(array_to_search[index_to_search + offset_idx].strip().split()[0])
    return dict_array_values[index_to_search]

def binary_find_left_segment_index(array_to_search: list[str], dict_array_values: dict, low: int, high: int,
                                   offset_array: int, element_to_search: float):
    """For example, given array [12, 20, 32, 40, 52]
	Value search: 5, result: 0
	Value search: 13, result: 1
	Value search: 20, result: 1
	Value search: 21, result: 2
	Value search: 51 or 52 result: 4
	Value search: 53, result: 5
	This is used to find the left index of the segment.
	:param array_to_search: Array to search
	:param dict_array_values: Dictionary to keep track of the wavelengths
	:param low: Where to start looking from
	:param high: Where to end looking from
	:param offset_array: Offset index to add to the index to search in the array
	:param element_to_search: Element to search
	:return: Left index of the segment
	"""
    # because we are using the upper bound, we need to subtract 1 from high or something
    # cant remember why, but it otherwise crashes. something about offset of 1
    high -= 1
    # if value to search is less than the first element, return low
    if element_to_search <= get_wavelength_from_array(array_to_search, dict_array_values, low, offset_array):
        return low
    # if value to search is greater than the last element, return high
    if element_to_search >= get_wavelength_from_array(array_to_search, dict_array_values, high, offset_array):
        return high

    left, right = 0, high

    while left <= right:
        mid = (left + right) // 2
        mid_value: float = get_wavelength_from_array(array_to_search, dict_array_values, mid + low, offset_array)

        if mid_value < element_to_search:
            left = mid + 1
        elif mid_value > element_to_search:
            right = mid - 1
        else:
            # If the exact value is found, check if it is the first occurrence.
            while mid > 0:
                if get_wavelength_from_array(array_to_search, dict_array_values, mid + low - 1, offset_array) == element_to_search:
                    mid -= 1
                else:
                    break
            return mid + low
    return left + low

def binary_find_right_segment_index(array_to_search: list[str], dict_array_values: dict, low: int, high: int,
                                    offset_array: int, element_to_search: float):
    """ For example, given array [12, 20, 32, 40, 52]
	Value search: 5, result: 0
	Value search: 13, result: 0
	Value search: 20, result: 1
	Value search: 21, result: 1
	Value search: 51 or 52 result: 3
	Value search: 53, result: 4
	This is used to find the right index of the segment.
	:param array_to_search: Array to search
	:param dict_array_values: Dictionary to keep track of the wavelengths
	:param low: Where to start looking from
	:param high: Where to end looking from
	:param offset_array: Offset index to add to the index to search in the array
	:param element_to_search: Element to search
	:return: Right index of the segment
	"""
    high -= 1
    if element_to_search <= get_wavelength_from_array(array_to_search, dict_array_values, low, offset_array):
        return low
    if element_to_search >= get_wavelength_from_array(array_to_search, dict_array_values, high, offset_array):
        return high

    left, right = 0, high - low

    while left < right:
        mid = (left + right) // 2
        if mid + low not in dict_array_values:
            dict_array_values[mid + low] = float(array_to_search[mid + low + offset_array].strip().split()[0])
        mid_value: float = dict_array_values[mid + low]

        if mid_value <= element_to_search:
            left = mid + 1
        else:
            right = mid
    return left + low - 1

def write_lines(indices_to_write: dict, lines_file: list[str], elem_line_1_to_save: str, elem_line_2_to_save: str,
                new_path_name: str, line_list_number: float):
    """
    Writes the lines to the new linelist file based on the indices of the lines to write.
    :param indices_to_write: Dictionary with the indices of the lines to write
    :param lines_file: List with all lines from the old linelist file
    :param elem_line_1_to_save: First line of the element
    :param elem_line_2_to_save: Second line of the element
    :param new_path_name: Path to the folder where the new linelists will be saved
    :param line_list_number: Number of the linelist
    """
    for key in indices_to_write:
        # if lbl, this goes through all segments, if not lbl, this goes through only one segment
        # key would be segment index if lbl, otherwise 0
        new_linelist_name: str = os.path.join(f"{new_path_name}", f"{key}", f"linelist-{line_list_number}.bsyn")
        with open(new_linelist_name, "a") as new_file_to_write:
            # now we append the lines to the new linelist. since we need to keep track of the line length, we do it here
            line_length = 0
            # we also keep track of the lines to write and then write them all at once
            lines_to_write = ""
            for index_pairs in indices_to_write[key]:
                # now we go through all the indices of the lines to write
                # for lbl this is just 1 pair, for not lbl this is all pairs
                index_start, index_end = index_pairs
                line_length += index_end - index_start
                lines_to_write += "".join(lines_file[index_start:index_end])
            new_file_to_write.write(f"{elem_line_1_to_save}	{line_length}\n")
            new_file_to_write.write(f"{elem_line_2_to_save}")
            new_file_to_write.write(lines_to_write)

def combine_linelists(line_list_path_trimmed: str, combined_linelist_name: str = "combined_linelist.bsyn", return_parsed_linelist: bool = False):
    parsed_linelist_data = []
    for folder in os.listdir(line_list_path_trimmed):
        if os.path.isdir(os.path.join(line_list_path_trimmed, folder)):
            # go into each folder and combine all linelists into one
            combined_linelist = os.path.join(line_list_path_trimmed, folder, combined_linelist_name)
            with open(combined_linelist, "w") as combined_linelist_file:
                for file in os.listdir(os.path.join(line_list_path_trimmed, folder)):
                    if file.endswith(".bsyn") and not file == combined_linelist_name:
                        with open(os.path.join(line_list_path_trimmed, folder, file), "r") as linelist_file:
                            read_file = linelist_file.read()
                            combined_linelist_file.write(read_file)
                            if return_parsed_linelist:
                                parsed_linelist_data.append(read_file)
                        # delete the file
                        os.remove(os.path.join(line_list_path_trimmed, folder, file))
    if return_parsed_linelist:
        return parsed_linelist_data

def read_element_data(lines):
    i = 0
    elements_data = []
    while i < len(lines):
        line_parts = lines[i].split()
        if len(line_parts) == 0:
            i += 1
            continue
        if line_parts[0] == "'":
            atomic_num = (line_parts[1])
        else:
            atomic_num = (line_parts[0])
        ionization = int(line_parts[-2])
        num_lines = int(line_parts[-1])

        element_name = lines[i + 1].strip().replace("'", "").replace("NLTE", "").replace("LTE", "")

        for _ in range(num_lines):
            i += 1
            data_line = lines[i + 1]
            wavelength, loggf = float(data_line.split()[0]), float(data_line.split()[2])
            #elements_data.append((element_name, atomic_num, ionization, wavelength, loggf))
            elements_data.append((wavelength, f"{element_name}", loggf))

        i += 2

    return elements_data

def find_elements(elements_data, left_wavelength, right_wavelength, loggf_threshold):
    filtered_elements = []
    for element_data in elements_data:
        wavelength, element_name, loggf = element_data
        if left_wavelength <= wavelength <= right_wavelength and loggf >= loggf_threshold:
            filtered_elements.append(element_data)

    sorted_elements = sorted(filtered_elements, key=lambda x: x[0])  # Sort by wavelength
    sorted_elements = [list(sorted_elements[i]) for i in range(len(sorted_elements))]
    return sorted_elements

    #for element_data in sorted_elements:
    #    element_name, atomic_num, ionization, wavelength, loggf = element_data
    #    print(element_name.replace("'", "").replace("NLTE", "").replace("LTE", ""), atomic_num, wavelength, loggf)


def find_element(elements_data, element_name):
    # ["wavelenght", "element name like 'FeI'", "log gf"]
    element_data = []
    for i in range(len(elements_data)):
        elements_data[i][1] = output_string = re.sub(r'\s+', ' ', elements_data[i][1].strip())
        print(elements_data[i][1])
        if elements_data[i][1] == element_name:
            element_data.append(elements_data[i])

    return element_data


if __name__ == "__main__":

    turbospectrum_paths = {"turbospec_path": "../turbospectrum/exec/",  # change to /exec-gf/ if gnu compiler
                        "interpol_path": "../scripts/model_interpolators/",
                        "model_atom_path": "../input_files/nlte_data/model_atoms/",
                        "departure_file_path": "../input_files/nlte_data/",
                        "model_atmosphere_grid_path": "../input_files/model_atmospheres/",
                        "line_list_path": "/home/alpha/TSFitPy/input_files/linelists/linelist_for_fitting"}


#    obs_data = obs_grab("20.tab.norm")
    synth_data = synt_grab("0.spec")

    lmin = synth_data[:, 0][0]
    lmax = synth_data[:, 0][-1]
    include_molecules = True

    today = datetime.datetime.now().strftime("%b-%d-%Y-%H-%M-%S")  # used to not conflict with other instances of fits
    today = f"{today}_{np.random.random(1)[0]}"
    temp_directory = f"../temp_directory/temp_directory_{datetime.datetime.now().strftime('%b-%d-%Y-%H-%M-%S')}__{np.random.random(1)[0]}/"
    line_list_path_trimmed = os.path.join(f"{temp_directory}", "linelist_for_fitting_trimmed", "")
    line_list_path_trimmed = os.path.join(line_list_path_trimmed, "all", today, '')

    create_window_linelist([lmin - 4], [lmax + 4], turbospectrum_paths["line_list_path"], line_list_path_trimmed, include_molecules, False, do_hydrogen=False)
    return_parsed_linelist = True
    parsed_linelist_data = combine_linelists(line_list_path_trimmed, return_parsed_linelist=return_parsed_linelist)
    parsed_elements_sorted_info = None
    if return_parsed_linelist:
        parsed_model_atom_data = []
        for i in range(len(parsed_linelist_data)):
            parsed_model_atom_data.extend(parsed_linelist_data[i].split("\n"))
        left_wavelength = lmin  # change this to change the range of wavelengths to print
        right_wavelength = lmax
        loggf_threshold = -1          # change this to change the threshold for loggf
        elements_data = read_element_data(parsed_model_atom_data)
        parsed_elements_sorted_info = find_elements(elements_data, left_wavelength, right_wavelength, loggf_threshold)

    print(parsed_elements_sorted_info)
    Fe1_list = find_element(parsed_elements_sorted_info, "Fe II")
    print(Fe1_list)



    save_graph = False
    show_graph = False

    if save_graph:
        import matplotlib.pyplot as plt
        import scienceplots
        
        with plt.style.context('science'):
            plt.figure()
            plt.plot(synth_data[:, 0], synth_data[:, 1], color="black")
            for line in parsed_elements_sorted_info:
                wl, element, log_gf = line
                plt.axvline(x=wl, color='gray', linestyle='--')
                plt.text(wl, 1 * 0.5, f'{element} (log gf={log_gf})', rotation=90, verticalalignment='bottom', color='black')
            plt.show()


        import plotly.express as px

        fig = px.line(x=synth_data[:, 0][::10], y=synth_data[:, 1][::10], title='Spectrum')
        fig.show()
    

    if show_graph:
        import plotly.graph_objects as go
        
        fig = go.Figure()

        wavelengths = synth_data[:, 0][::10]
        intensities = synth_data[:, 1][::10]

        fig.add_trace(go.Scatter(x=wavelengths, y=intensities, mode='lines', name='Spectrum'))

        for line in parsed_elements_sorted_info:
            wl, element, log_gf = line
            fig.add_trace(go.Scatter(x=[wl, wl], y=[min(intensities), 1.05], mode='lines', 
                                    line=dict(color='black', dash='dash'), name=f'{element} (log gf={log_gf})'))
            fig.add_annotation(x=wl, y=max(intensities) * 1.05, text=f'{element} (log gf={log_gf})',
                            showarrow=True, xshift=0, yshift=0, textangle=-90, font=dict(color='black'))

        # Настройка осей и заголовка
        fig.update_layout(title='Спектральные линии химических элементов',
                        xaxis_title='Длина волны (нм)',
                        yaxis_title='Интенсивность')

        fig.show()