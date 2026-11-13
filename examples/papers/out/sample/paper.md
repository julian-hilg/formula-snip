<!-- page 1 -->

# A Two-Page Note on Option Pricing

## Formula Snip example

# 1 The Black–Scholes model

Let  $S_t$  be the price of a stock that follows a geometric Brownian motion with drift  $\mu$  and volatility  $\sigma$ . The price of a European call option with strike  $K$  and maturity  $T$  is

$$C = S_0 N(d_1) - K e^{-rT} N(d_2), \tag{1}$$

where  $r$  denotes the risk-free interest rate and  $N$  is the standard normal distribution function. The two arguments are

$$d_1 = \frac{\ln(S_0/K) + (r + \sigma^2/2)T}{\sigma\sqrt{T}} \tag{2}$$

and

$$d_2 = d_1 - \sigma\sqrt{T}. \tag{3}$$

Put-call parity links the call to the put price  $P$  through  $C - P = S_0 - K e^{-rT}$ .

## 2 Risk and return

The capital asset pricing model states that

$$\mathbf{E}[R_i] = r_f + \beta_i (\mathbf{E}[R_m] - r_f), \tag{4}$$

where  $r_f$  is the risk-free rate and  $\beta_i$  is the sensitivity of asset  $i$  to the market. The Sharpe ratio of a portfolio with mean return  $\mu_p$  and volatility  $\sigma_p$  is

$$SR = \frac{\mu_p - r_f}{\sigma_p}. \tag{5}$$

| Asset   | $\beta_i$ | Sharpe ratio |
|---------|-----------|--------------|
| Stock A | 0.80      | 0.42         |
| Stock B | 1.20      | 0.35         |
| Stock C | 1.50      | 0.28         |

Table 1: Example betas and Sharpe ratios.

<!-- page 2 -->

A cash flow  $X$  received at time  $T$  is worth  $Xe^{-rT}$  today. With annual compounding at rate  $y$  the present value of a bond paying coupon  $c$  for  $n$  years and face value  $F$  is

### 3 Discounting

$$PV = \sum_{k=1}^n \frac{c}{(1+y)^k} + \frac{F}{(1+y)^n}. \tag{6}$$

The continuously compounded return over a period is  $\ln(S_T/S_0)$ , and its expected value under the risk-neutral measure is  $(r - \sigma^2/2)T$ .
