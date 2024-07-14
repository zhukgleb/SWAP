from numpy import genfromtxt, ndarray

def synt_grab(path2data: str) -> ndarray:
    return genfromtxt(path2data, comments="#")


def obs_grab(path2data: str) -> ndarray:
    return genfromtxt(path2data)


if __name__ == "__main__":
    data = synt_grab("0.spec")
    print(data)