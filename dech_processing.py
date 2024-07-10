"""
A small module of various functions for working with dech20/95 output files
"""

from numpy import genfromtxt, concatenate, column_stack, savetxt, ndarray


"""
There in Dech is an option to choose to save all orders at once into one file,
but in this case all orders will not be saved in order,
but written down in a column, which creates a little confusion
"""
def tab_spectra(filepath: str, save=False) -> ndarray:
    data = genfromtxt(filepath)
    all_wave = []
    all_flux = []
    
    for i in range(0, len(data[0]), 2):
        all_wave.append(data[:, i])

    for i in range(1, len(data[0]), 2):
        all_flux.append(data[:, i])

    conc_wave = concatenate(all_wave)
    conc_flux = concatenate(all_flux)
    output =  column_stack((conc_wave, conc_flux))
    
    if save:
        savetxt("filepath" + "concat.txt", output)
    else:
        return output


if __name__ == "__main__":
    data = tab_spectra("dech30.tab")
    print(data)