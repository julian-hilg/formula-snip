

{0}------------------------------------------------

## <span id="page-0-0"></span>1. Introduction

Asian options are derivatives with payoff linked to the time average of the asset price

$$(1) \quad A_T := \frac{1}{T} \int_0^T S_t dt.$$
We price them under the Black-Scholes model, where the asset price follows a geometric Brownian motion

$$(2) \quad \frac{dS_t}{S_t} = (r - q)dt + \sigma dW_t,$$

where  $r$  denotes the risk-free rate,  $q$  is the dividend yield and  $\sigma$  is the volatility. See [\[8\]](#page-15-0) for a survey.

{1}------------------------------------------------

## 2. Pricing

Let  $S_t$  be the price of the stock at time  $t$ . The call price is

$$C = S_0 N(d_1) - K e^{-rT} N(d_2), \qquad (3)$$

with  $K$  the strike and

$$d_1 = \frac{\ln(S_0/K) + (r + \sigma^2/2)T}{\sigma\sqrt{T}}.$$

The rate function is

$$(2.1) \quad J_{\text{BS}}(k) = \begin{cases} \frac{1}{2}\beta^2 & , k \geq 1 \\ 2\xi^2 & , k < 1 \end{cases}$$

where  $\beta$  and  $\xi$  are the solutions of two equations.

| Asset | $\beta_i$ | Return |
|-------|-----------|--------|
| A     | 0.8       | 5%     |

```python
x = "$not math$"
```

Its expansion is  $J(k) = \frac{3}{2}\log^2 k + O(\log^3 k)$  for  $k$  near one.
