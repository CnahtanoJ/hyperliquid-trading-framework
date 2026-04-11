import pandas as pd

class VectorStrategy:
    """
    Base class for all strategies.
    Implement get_signal_column to define strategy logic.
    """
    def get_signal_column(self, df: pd.DataFrame) -> pd.Series:
        """
        Returns a series of signals:
        1: Buy / Long
        -1: Sell / Short
        2: Exit / Flat
        0: Hold current position
        """
        raise NotImplementedError("Each strategy must implement get_signal_column")
