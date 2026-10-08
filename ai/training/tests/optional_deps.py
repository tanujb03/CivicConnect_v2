"""Skip markers for the optional training packages (``pip install -e "ai[training]"``).

A probe instead of ``find_spec``: on some Windows machines an Application Control policy blocks scikit-learn's compiled ``_libsvm`` DLL, so the package is
installed but its import raises ``ImportError`` ("DLL load failed"). That counts as unavailable too, and the reason is shown in the skip message.
"""
import pytest


def _probe(statement: str) -> str | None:
    try:
        exec(statement, {})
    except ImportError as exc:
        return f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else statement}"
    return None


SKLEARN_PROBLEM = _probe("from sklearn.linear_model import LogisticRegression")
SCIPY_PROBLEM = _probe("from scipy.optimize import minimize; from scipy.sparse import csr_matrix")

requires_sklearn = pytest.mark.skipif(SKLEARN_PROBLEM is not None, reason=f"scikit-learn is not usable ({SKLEARN_PROBLEM}); install ai[training]")
requires_scipy = pytest.mark.skipif(SCIPY_PROBLEM is not None, reason=f"scipy is not usable ({SCIPY_PROBLEM}); install ai[training]")
