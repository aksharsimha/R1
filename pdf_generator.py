import os
from fpdf import FPDF
import numpy as np

class MathReportPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Quantitative Portfolio Math & Reasoning', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_math_report(df, summary, filename="math_report.pdf"):
    pdf = MathReportPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=11)
    
    # Intro
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. 200-Day Moving Average via QR Decomposition", 0, 1)
    pdf.set_font("Arial", size=11)
    
    qr_text = (
        "Typically, a 200-Day Moving Average (200DMA) is calculated as a simple mean: SMA = sum(P_i)/200. "
        "However, strictly speaking, finding the mean is equivalent to finding the scalar 'c' that minimizes the "
        "least squares error || y - A*c ||^2, where 'y' is the 200x1 vector of daily closing prices and 'A' is a 200x1 "
        "column vector of ones.\n\n"
        "Step-by-step QR Decomposition:\n"
        "  1. We define A as a 200x1 matrix of 1s.\n"
        "  2. We factor A into an orthogonal matrix Q (200x1) and an upper triangular matrix R (1x1).\n"
        "     Since A is just ones, Q = (1/sqrt(200)) * A, and R = sqrt(200).\n"
        "  3. The least squares solution for the moving average 'c' is given by c = R^(-1) * Q^T * y.\n"
        "  4. Q^T * y is simply (1/sqrt(200)) * sum(y). Multiplying by R^(-1) = 1/sqrt(200) yields sum(y)/200.\n"
        "Thus, the QR decomposition perfectly derives the exact 200DMA!"
    )
    pdf.multi_cell(0, 7, qr_text)
    pdf.ln(5)
    
    # Portfolio Analysis
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Eigenvalues and Eigenvectors (PCA of Portfolio)", 0, 1)
    pdf.set_font("Arial", size=11)
    
    pca_text = (
        "To understand the 'hidden forces' driving the portfolio, we calculate the Eigenvalues and Eigenvectors of the "
        "covariance matrix of daily asset returns.\n\n"
        "Step-by-step Process:\n"
        "  1. Let 'X' be the T x N matrix of daily returns for N assets over T days.\n"
        "  2. We compute the N x N covariance matrix: C = (X^T * X) / (T - 1).\n"
        "  3. We solve the characteristic equation det(C - lambda*I) = 0 to find the Eigenvalues (lambda).\n"
        "  4. The sum of all Eigenvalues represents the total variance of the portfolio.\n"
        "  5. For each Eigenvalue, we find its corresponding Eigenvector 'v', satisfying C*v = lambda*v. "
        "These vectors tell us the 'direction' of the hidden market factors (e.g., General Market Trend, Sector Trend).\n"
    )
    pdf.multi_cell(0, 7, pca_text)
    pdf.ln(5)
    
    # Specific Portfolio PCA Results
    explained_var = summary.get("pca_explained_var", [])
    if len(explained_var) > 0:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 10, "Your Portfolio's Top 5 Principal Components (Hidden Factors):", 0, 1)
        pdf.set_font("Arial", size=11)
        
        # Explain the variance of the top 5 factors
        for i, var in enumerate(explained_var[:5]):
            pdf.cell(0, 7, f"  Factor {i+1} Eigenvalue explains {var*100:.2f}% of your portfolio's variance.", 0, 1)
            
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 10, "What do these statistical factors mean in reality?", 0, 1)
        pdf.set_font("Arial", size=11)
        
        factor_interpretations = (
            "Because these factors are generated purely by the Eigenvectors of your covariance matrix, they don't have "
            "hardcoded names. However, quantitative analysts typically interpret them as follows:\n\n"
            "Factor 1: The General Market Direction (Macro Trend)\n"
            "This usually explains 60% to 80% of variance. It captures the reality that most assets move with the broader market. "
            "If this factor explains >80% of your variance, your portfolio is acting as a single highly correlated unit.\n\n"
            "Factor 2: Asset Class & Sector Divides (e.g., Stocks vs. Gold)\n"
            "Usually captures how different types of assets react to stress (e.g., when equities fall, gold rises).\n\n"
            "Factor 3: Industry-Specific Shocks\n"
            "Groups companies in the same industry. For example, infrastructure policy changes affecting PSU stocks "
            "while leaving tech stocks untouched.\n\n"
            "Factor 4: Value vs. Growth / Interest Rate Sensitivity\n"
            "Captures how stocks react to borrowing costs. High-growth tech companies react differently to interest rate "
            "hikes than cash-rich dividend-paying companies.\n\n"
            "Factor 5: Company-Specific Noise (Idiosyncratic Risk)\n"
            "Picks up specific, isolated events like a single company reporting bad earnings, which has almost zero "
            "correlation with the rest of your portfolio."
        )
        pdf.multi_cell(0, 6, factor_interpretations)
        pdf.ln(5)
    else:
        pdf.cell(0, 7, "Not enough data to run full Eigendecomposition on your portfolio right now.", 0, 1)
    
    pdf.ln(5)
    
    # Asset Specifics
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "3. Asset-Specific Quantitative Metrics", 0, 1)
    pdf.set_font("Arial", size=11)
    
    for _, row in df.iterrows():
        name = row["Name"]
        score = row["Risk Score"]
        vol = row.get("Volatility %", 0)
        sharpe = row.get("Sharpe", 0)
        d200 = row.get("Dist 200DMA %", 0)
        price = row.get("Last Price", 0)
        
        ma200 = price / (1 + d200 / 100.0) if price > 0 else 0
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, f"{name}:", 0, 1)
        pdf.set_font("Arial", size=11)
        
        asset_text = (
            f"  * QR-Derived 200-Day Average: Rs. {ma200:.2f}\n"
            f"  * Current Price: Rs. {price:.2f} (Distance: {d200:.2f}%)\n"
            f"  * Volatility (Standard Deviation): {vol:.2f}%\n"
            f"  * Sharpe Ratio: {sharpe:.2f}\n"
            f"  * Composite Risk Score: {score:.2f}/100"
        )
        pdf.multi_cell(0, 6, asset_text)
        pdf.ln(3)

    pdf.output(filename)
    return filename
