<!-- page 1 -->

# An Explicit Solution to Black–Scholes Implied Volatility

Wolfgang Schadner\* <sup>†</sup>

May 19, 2026

Black-Scholes implied volatility is a quantile. The insight follows from the normalized option price being a probability on the variance scale, with the inverse Gaussian distribution providing the link. It enables analytically exact and explicit formulas for implied volatility in terms of existing quantile functions, with volatility on the left-hand side and only observable option inputs on the right-hand side. The result is not another approximation or asymptotic expansion. Instead, it rewrites the price-to-volatility map itself as a distributional transform. The representation gives implied volatility a first-passage-time interpretation, identifies variance as the natural coordinate of inversion, and reorganizes Greeks and no-arbitrage restrictions in the same variance-quantile coordinates. Numerically, the formula achieves machine precision faster than a state-of-the-art solver in the benchmark considered. The paper therefore provides a new coordinate system for computing, interpreting, and decomposing one of the central quantities in option markets.

## Abstract

**Keywords:** option markets, implied volatility, Black–Scholes, inverse Gaussian

**JEL Classification:** G13; C58

---

\*University of Liechtenstein, wolfgang.schadner@uni.li.

<sup>†</sup>I am grateful to Tomasz Dubiel-Teleszynski for many helpful discussions and to Michael Hanke for valuable feedback.

<!-- page 2 -->

# 1 Introduction

The Black–Scholes formula is explicit from volatility to option price. Market practice, however, needs the reverse map, from an observed option price to the implied volatility that reproduces it. Since Black and Scholes (1973), implied volatility has become the standard convention for quoting and comparing option prices across strikes, maturities, assets, and dates. It is used throughout derivatives markets, empirical asset pricing, volatility forecasting, risk management, option-return studies, tests of volatility risk premia, and quantification of forward-looking investor expectations. Implied volatility  $\sigma$  is therefore not simply a model parameter but the standard coordinate in which option markets are measured, traded and managed. Yet the step from price to implied volatility has remained an analytical black box. For a normalized call price  $c = C/D/F$ , with  $D$  the risk-free discount,  $F$  the forward, and moneyness  $k = \log K/F$  at strike  $K$ , the general form is

$$\sigma(k, c) = \frac{2}{\sqrt{T}} Q_k^{-1} \left( \frac{1+c}{2} \right). \tag{1}$$

The inverse function  $Q_k^{-1}(\cdot)$  is explicitly known for the at-the-forward strike  $k = 0$  as the simple normal quantile,  $Q_0^{-1}(\cdot) = \Phi^{-1}(\cdot)$ , but its general form for all strikes has remained an unsolved puzzle. The literature trying to solve it grew large over the last five decades. A first strand derives approximations, including Brenner and Subrahmanyam (1988); Corrado and Miller (1996); Li (2008) and Stefanica and Radoičić (2017). A second strand studies bounds to pin the problem down to a feasible region (Tehranchi (2016); Gatheral et al. (2017)) or large-strike asymptotics to reveal the structural restrictions (Lee, 2004; Gao and Lee, 2014). A third strand develops numerical or semi-analytical inversion methods, including the highly accurate iterative algorithms of Jäckel (2015, 2024) and the series-based representation of Cui et al. (2021). These methods are accurate but represent the inverse algorithmically, iteratively, or through an infinite expansion. Beyond these constructive strands, Gerhold (2012) showed that implied volatility must be *some* non- $D$ -finite function, ruling out a broad class of closed-form representations. This paper identifies *which* non- $D$ -finite function it is. Let  $\mathcal{F}_{IG}^{-1}$  denote the quantile function of the inverse Gaussian distribution, the core insight

<!-- page 3 -->

is

$$Q_k^{-1} \left( \frac{1+c}{2} \right) = \frac{1}{\sqrt{\mathcal{F}_{IG}^{-1} \left( \frac{1-c}{\eta_k}, \frac{2}{|k|}, 1 \right)}}, \tag{2}$$

with  $\eta_k = \min(1, e^k)$  marking whether the option is out-of-the-money ( $\eta_k = 1$  for  $k \geq 0$ ) or in-the-money ( $\eta_k = e^k$  for  $k < 0$ ). The formula places implied volatility on the left-hand side and only observable market data on the right-hand side. It identifies the distributional quantile hidden in the inverse Black–Scholes map and gives implied volatility a probabilistic interpretation. Equivalently, implied variance is a quantile of a generalized inverse Gaussian law. The option price is a probability, implied variance the corresponding quantile, variance-vega the density, and the static no-arbitrage restrictions are sign conditions on the same probability map. Variance is in this sense the natural coordinate of inversion, where the call price equals a standard probability law.

Computationally, the outer Black–Scholes inversion is replaced by the evaluation of a specified inverse Gaussian quantile. This does not mean numerical work disappears, since quantile functions are themselves evaluated numerically. The point is that the inverse problem is transferred from the option-pricing map to a probability law, where it is better conditioned: variance is the natural inversion coordinate, and the conditioning gain is large precisely in the low-volatility regime where the volatility-space inverse is most fragile. In the numerical tests below, this representation recovers implied volatility to machine precision faster than Jäckel (2024)’s implementation on the benchmark considered (a high-accuracy reference method, see also Matić et al., 2020; vollib, 2023), with a single Halley refinement sufficing in place of two higher-order steps in volatility space.

The remainder of the paper is organized as follows. Section 2 derives the variance-quantile representation. Section 3 develops three interrelated implications. Section 4 reports the numerical benchmark. And section 5 concludes. Together, this work demonstrates that the pricing map, its inverse, the Greeks, and the no-arbitrage restrictions are all expressions of the same variance-quantile structure.

<!-- page 4 -->

## 2 Implied Volatility is a Quantile

This section starts with the derivation of Black–Scholes implied volatility as an exact formula of existing quantile functions. Let  $v = \sigma\sqrt{T}$  be the total implied volatility. The normalized Black–Scholes European call price is

$$c_{BS}(k, v) = \Phi\left(-\frac{k}{v} + \frac{v}{2}\right) - e^k \Phi\left(-\frac{k}{v} - \frac{v}{2}\right). \tag{3}$$

The case  $k = 0$  collapses to  $c_{BS}(0, v) = 2\Phi(v/2) - 1$ , hence the known solution for at-the-forward. It remains to consider  $k \neq 0$ . First, take an out-of-the-money call, so  $k > 0$ . Write  $\mathcal{F}_{IG}(\cdot; \mu, \lambda)$  for the inverse Gaussian distribution function with mean parameter  $\mu$  and shape parameter  $\lambda$ , following the standard parametrization in Chhikara and Folks (1989). Its survival function is

$$1 - \mathcal{F}_{IG}(x; \mu, \lambda) = \Phi\left(-\frac{\sqrt{\lambda}x}{\mu} + \frac{\sqrt{\lambda}}{\sqrt{x}}\right) - e^{2\lambda/\mu} \Phi\left(-\frac{\sqrt{\lambda}x}{\mu} - \frac{\sqrt{\lambda}}{\sqrt{x}}\right). \tag{4}$$

With  $\lambda = 1$ ,  $\mu = 2/k$ , and  $x = 4/v^2$ , this becomes

$$c_{BS}(k, v) = 1 - \mathcal{F}_{IG} \left( \frac{4}{v^2}; \frac{2}{k}, 1 \right), \quad k > 0, \tag{5}$$

inverting Eq. (5) and using  $\sigma = v/\sqrt{T}$  gives

$$\sigma(k, c) = \frac{2}{\sqrt{T}} \frac{1}{\sqrt{\mathcal{F}_{IG}^{-1} \left(1 - c; \frac{2}{k}, 1\right)}}, \quad k > 0. \tag{6}$$

**In-the-money and Put.** For  $k < 0$ , the call  $c$  is in the money. It is related to the out-of-the-money counterpart  $\tilde{c}$  of same volatility and log-moneyness  $-k$  by

$$1 - \tilde{c} = \frac{1 - c}{K/F}. \tag{7}$$

<!-- page 5 -->

Hence, a division by gross moneys  $K/F = e^k$  projects the ITM call back to the OTM region,  $\eta_k$  in Eq. (2) is just a formal handling of that.<sup>1</sup>

The corresponding put formula follows from put-call parity,

$$c - p = 1 - e^k. \tag{8}$$

For a put with normalized price  $p = P/D/F$  and  $k \neq 0$ , the probability argument in the inverse Gaussian quantile is  $(e^k - p)/\eta_k$ . Hence the put implied volatility is

$$\sigma(k, p) = \frac{2}{\sqrt{T}} \frac{1}{\sqrt{\mathcal{F}_{IG}^{-1} \left( \frac{e^k - p}{\eta_k}, \frac{2}{|k|}, 1 \right)}}. \tag{9}$$

**Pure Quantile.** Besides  $\sigma$ , another important metric is total implied variance  $w = \sigma^2 T$ . It is commonly used for no-arbitrage calibrations and Dupire formula for local volatilities (Gatheral, 2006). The above insight allows to express implied variance directly as a quantile. For this purpose, observe that we can establish an equivalent representation between the inverse Gaussian  $IG$  and the generalized inverse Gaussian distribution  $GIG$ ,

$$1 - \mathcal{F}_{IG}\left(\frac{4}{w}; \frac{2}{k}, 1\right) = \mathcal{F}_{GIG}\left(w, \frac{1}{2}, \frac{1}{4}, k^2\right) \tag{10}$$

(see Jørgensen (1982); Embrechts (1983) for details). For simplicity I focus on the OTM branch. The generalized form is especially appealing because it shows that implied variance  $w$  is a pure quantile of the  $GIG$  family,

$$w = \mathcal{F}_{GIG}^{-1}(c; \frac{1}{2}, \frac{1}{4}, k^2), \quad k > 0. \tag{11}$$

<sup>1</sup>To see this, use Eq. (3) to express  $\tilde{c}$  under a flipped sign of  $k$ . Note that  $\Phi\left(\frac{k}{v} + \frac{v}{2}\right) = 1 - \Phi\left(-\frac{k}{v} - \frac{v}{2}\right)$ , so rearranging terms and substituting  $c$  gives Eq. (7). A smooth definition of  $\eta_k$  is  $\eta_k := e^{(|k|)/2}$ , which is identical to  $\eta_k = \min(1, e^k)$ .

<!-- page 6 -->

Similarly, because  $\sigma$  is an increasing function of  $w$ , implied volatility is also a quantile. Specifically,

$$\sigma = \mathcal{F}_{\sqrt{Z_k/T}}^{-1}(c), \quad k > 0, \tag{12}$$

where  $Z_k \sim GIG(\frac{1}{2}, \frac{1}{4}, k^2)$  is a strike-dependent *GIG* random variable. Knowing the inverse Gaussian structure, it is straightforward to write the same inverse in alternative representations. Appendix A.1 collects various equivalent forms. The incomplete Gamma, incomplete Bessel- $K$ , tilted Levy, tilted Chi-square and tilted Gamma representations all invert directly in total variance. The tilted half-normal/Nakagami representation restates the same identity in total volatility by applying the square-root map to the variance law. Its tilt term depends on inverse variance, so its probabilistic content also remains nested in variance space. So, the volatility quantile is a projection of the variance quantile.

The above result comes with two notable insights. First, implied volatility is not merely the output of a root-solving problem, but can be viewed as a quantile of a moneyness-specific distribution. Second, variance, not volatility, appears to be the natural coordinate of inversion. It is the coordinate in which the normalized call price equals a standard probability law.

### **3 Selected Implications**

The quantile representation has three related implications. It first gives normalized option prices a probabilistic interpretation on a variance scale. In the same coordinates, the Black–Scholes Greeks become derivatives of that probability law. These derivatives then provide the objects from which the calendar and butterfly no-arbitrage restrictions are built.

### 3.1 Probabilistic Interpretation

The quantile formula gives the call price a variance-space probability interpretation. This differs from return-space readings. For example, delta can be viewed as the probability that the terminal return clears the strike hurdle. Carr and Madan (2009) show that call prices can also be given a return-space probability interpretation under a suitable change of measure.

<!-- page 7 -->

The additional point here is that the normalized option price is also a probability level on a variance scale. Focusing on the OTM call branch  $k > 0$ , and keeping  $w = v^2$ ,

$$c_{BS}(k, v) = \mathbb{P} \left( Y_k > \frac{4}{w} \right), \quad Y_k \sim IG \left( \frac{2}{k}, 1 \right). \tag{13}$$

Let  $B_t$  denote standard Brownian motion and define

$$\tau_k = \inf \left\{ t > 0 : B_t + \frac{k}{2}t = 1 \right\}. \tag{14}$$

Then  $\tau_k \sim IG(2/k, 1)$ , so  $Y_k$  has the same law as the first hitting time of level 1 by a Brownian motion with drift  $k/2$  and unit diffusion volatility. Hence the normalized call price is the probability that this process has not yet hit level 1 by variance-clock time  $4/w$ . Total implied variance  $w$  thus plays the role of a speed in the first-passage picture—larger  $w$  runs the variance clock faster against the fixed budget 4, shortening the time available to hit level one. Equivalently, with  $Z_k = 4/Y_k$ ,

$$c_{BS}(k, v) = \mathbb{P}(Z_k \leq w), \quad Z_k \sim GIG\left(\frac{1}{2}, \frac{1}{4}, k^2\right). \tag{15}$$

Here  $Z_k$  is the variance budget the drifted Brownian motion requires to reach level one, so the call price is the probability that this required budget falls within what the implied variance  $w$  supplies. The market price fixes the probability level, and the implied total variance is the corresponding quantile of  $Z_k$ .

### 3.2 Greeks in Variance-Space

The variance-space representation also gives a compact organization of the Black–Scholes Greeks. Focus on the OTM call branch  $k > 0$ , the remaining cases follow from the transformations used above. Let  $f_k$  denote the density of  $Z_k \sim GIG(\frac{1}{2}, \frac{1}{4}, k^2)$ , and write the primitive Black–Scholes price in variance coordinates as  $c_{BS}(k, w)$ . All partial derivatives

<!-- page 8 -->

below are taken with respect to  $(k, w)$  with arguments suppressed.

variance-volga  $\partial_{ww} c_{BS} = f_k(w) \left( -\frac{1}{2w} - \frac{1}{8} + \frac{k^2}{2w^2} \right),$  (17)

variance-vega  $\partial_w c_{BS} = f_k(w),$  (16)

variance-vanna  $\quad \partial_{kw} c_{BS} = f_k(w) \left( \frac{1}{2} - \frac{k}{w} \right), \quad (18)$

moneyness sensitivity  $\quad \partial_k c_{BS} = \int_0^w f_k(x) \left( \frac{1}{2} - \frac{k}{x} \right) dx, \quad (19)$

$$\text{moneyness curvature} \quad \partial_{kk} c_{BS} = \int_0^w f_k(x) \left[ \left( \frac{1}{2} - \frac{k}{x} \right)^2 - \frac{1}{x} \right] dx. \tag{20}$$

This does not introduce new Greeks and does not change their economic meaning, what changes is representation. The standard Black–Scholes sensitivities, traditionally written as combinations of  $\Phi$  and  $\phi$ , become derivatives of a single probability law. Variance-vega is the *GIG* density itself, and the higher local sensitivities are the same density weighted by terms at most quadratic in  $1/w$  and  $k/w$ . This is cleaner than the corresponding volatility Greeks, where the square-root change of coordinates pulls in additional factors. The same hierarchy organizes the no-arbitrage conditions of the next subsection.

### 3.3 No-arbitrage in Variance-Space

The variance-space representation rewrites the standard calendar and butterfly conditions in the coordinates generated by the quantile formula. Pricing, inversion, Greeks, and static no-arbitrage are not separate objects in this representation, they are different derivatives of the same variance-space law. The observed call surface is  $c(k, T)$  and the total implied-variance surface is  $w(k, T)$ , linked by  $c(k, T) = c_{BS} \left( k, \sqrt{w(k, T)} \right)$ . At a fixed point, write  $w = w(k, T)$ . Subscripts on  $c$  and  $w$  denote derivatives of the observed surfaces. All derivatives of  $c_{BS}$  below are variance-coordinate derivatives, evaluated at the current  $(k, w)$ , with arguments suppressed.

**Calendar.** Calendar no-arbitrage has a particularly direct interpretation. At fixed log-moneyness, maturity changes the variance threshold while the variance-space distribution

<!-- page 9 -->

remains fixed. Therefore, for  $T_2 > T_1$ ,

$$c(k, T_2) - c(k, T_1) = \mathbb{P} (w(k, T_1) < Z_k \leq w(k, T_2)). \tag{21}$$

Thus, calendar spread can now be read as a probability band in variance space. Equivalently,  $c_T = \partial_w c_{BS} w_T = f_k(w) w_T$ , and since  $f_k(w) > 0$ , calendar no-arbitrage is equivalent to  $w_T \geq 0$ , matching the standard monotonicity condition for total implied variance (cp. Gatheral (2006)).

**Butterfly.** Butterfly no-arbitrage admits two equivalent representations in variance coordinates, one read from the price side and one from the quantile side. In the forward direction, the chain rule along the observed surface expresses  $c_k$  and  $c_{kk}$  as combinations of the variance-Greeks and the smile derivatives  $w_k, w_{kk}$ . Substituting into the butterfly condition  $c_{kk} \geq c_k$  yields

$$\partial_{kk}c_{BS} - \partial_k c_{BS} + (2\partial_{kw}c_{BS} - \partial_w c_{BS}) w_k + \partial_{ww}c_{BS} w_k^2 + \partial_w c_{BS} w_{kk} \geq 0. \tag{22}$$

Butterfly no-arbitrage is therefore a sign condition on the same Greek hierarchy from above—moneyness sensitivity, moneyness curvature, variance-vega, variance-vanna, variance-volga—combined with the slope  $w_k$  and curvature  $w_{kk}$  of the variance smile (cp. Gatheral and Jacquier (2014)).

In the inverse direction, the variance quantile map  $q(k, u) := \mathcal{F}_{GIG}^{-1}(u; \frac{1}{2}, \frac{1}{4}, k^2)$  inverts the price-to-variance step, giving  $w = q(k, c)$  with  $q_u = 1/f_k > 0$ . The chain rule in  $(k, c)$ -coordinates substituted into  $c_{kk} \geq c_k$  yields

$$w_{kk} \geq q_{kk} + 2q_{ku}c_k + q_{uu}c_k^2 + q_uc_k. \tag{23}$$

Butterfly no-arbitrage is now a quadratic lower bound on the implied-variance curvature  $w_{kk}$  in terms of the observed call slope  $c_k$ , with coefficients given by partials of the variance quantile map. The two are equivalent restrictions on the same surface, read from opposite sides of the variance-space coordinate system. The forward form is natural when starting from a parametric variance smile, the inverse form is natural when starting from observed option prices.

<!-- page 10 -->

## 4 Numerical Evaluation

The numerical implementation is based on the *GIG* quantile, where all options are projected to the OTM call branch. As benchmark I use Jäckel (2024)'s *Let's Be Rational* (LBR), accessed through its native shared-library interface. It is a state-of-the-art implementation of Black-Scholes implied-volatility inversion that is both extremely fast and designed to recover implied volatility to essentially full double-precision accuracy within two iterations. The main structural difference is the inversion coordinate. LBR solves directly in total volatility  $v$ , while the present implementation solves in total variance  $w$  and takes the square root only at the end.

The numerical reason for using  $w$  can be stated without introducing separate price maps. For fixed  $k$ , with  $w = v^2$ ,

$$\left. \frac{\partial w}{\partial c} \right|_k = \frac{1}{\partial_w c_{BS}} \quad \text{and} \quad \left. \frac{\partial v}{\partial c} \right|_k = \frac{1}{\partial_v c_{BS}} = \frac{1}{2v \partial_w c_{BS}}. \tag{24}$$

The volatility-space inverse therefore carries the extra factor  $1/(2v)$ , which becomes large when  $v$  is small. For example, at  $v = 20\%$  it is 2.5, at  $v = 5\%$  it is 10, and at  $v = 1\%$  it is 50. This is not only a chain-rule artifact. The variance structure is already present in the classical Black–Scholes vega,

$$\partial_v c_{BS} = \phi\left(-\frac{k}{v} + \frac{v}{2}\right) = \frac{e^{k/2}}{\sqrt{2\pi}} \exp\left(-\frac{v^2}{8} - \frac{k^2}{2v^2}\right). \tag{25}$$

The variance term  $-k^2/(2v^2)$  sits inside the standard normal density. The same asymmetry appears in Newton refinement,

$$\Delta v = -\frac{c_{BS} - c}{\partial_v c_{BS}} = -\frac{c_{BS} - c}{2v \partial_w c_{BS}}. \tag{26}$$

Halley and higher-order Householder methods inherit analogous inverse powers of  $v$  through their higher derivatives. On the OTM branch, the inverse problem is therefore more naturally conditioned in variance space, especially for small total volatility.

I implement the variance-space inversion as an optimized rational seed for the *GIG* quantile followed by a single Halley refinement. Compared to the LBR pipeline it saves on two fronts. First, only one refinement step is used rather than two, sparing the more

<!-- page 11 -->

expensive part of the per-evaluation cost. Second, each refinement step is itself cheaper, because Halley is one order lower than the higher-order Householder iteration LBR uses, so fewer derivatives are evaluated per step. The quantile formula is evaluated on a randomized grid. Total volatility is drawn uniformly from [0.01, 2.00] and Black–Scholes call delta is drawn uniformly from [0.01, 0.99], giving 100,000 random test cases. For each draw  $(v, \Delta)$ , the corresponding forward log-moneyness is obtained from the Black–Scholes delta relation,

$$k = v \left( \frac{v}{2} - \Phi^{-1}(\Delta) \right). \tag{27}$$

The normalized call price is then generated from Eq. (3). On this random grid I examine both recovery accuracy and computation speed. Accuracy is measured by applying each inversion method to the generated price and comparing the recovered total volatility with the original input value. Speed is measured on repeated evaluations of that grid. One timing run consists of evaluating the 100,000 random cases 10 times, corresponding to 1,000,000 implied-volatility evaluations per method. Timings are recorded over 10 runs, so the full timing experiment comprises 10,000,000 evaluations per method. The experiment was run on an 11th Gen Intel Core i5-1145G7 processor at 2.60 GHz, using GCC under Linux/WSL2, with both routines evaluated as native compiled C++ code. The code used for the numerical experiments will be made available as online supplementary material upon publication.

On the randomized accuracy test, both methods recover total volatility to near machine precision. The median absolute recovery errors are  $1.39 \times 10^{-16}$  for the explicit formula and  $1.67 \times 10^{-16}$  for LBR, while the maximum absolute errors are  $1.33 \times 10^{-15}$  and  $1.55 \times 10^{-15}$ , respectively. On the speed test, the explicit formula requires 59.49 nanoseconds per evaluation at the median run, compared with 180.03 nanoseconds for LBR, implying a median speed ratio of about  $180.03/59.49 \approx 3.03$ . Using the maximum timing observed across runs yields 63.16 nanoseconds versus 182.78 nanoseconds. The LBR timing is also very close to the value in Jäckel (2024), where it is benchmarked at about 180 nanoseconds per implied-volatility evaluation. Table 1 summarizes the random-grid results, and Figure 1 displays the error and timing distributions.

<!-- page 12 -->

![](images/page_12_figure_0.jpg)

Figure 1: Random-grid benchmark summary. The left panel reports boxplots of the absolute recovery error of the explicit formula across volatility buckets. The right panel reports the run-level timing distribution for the explicit formula and Jäckel (2024)’s *Let’s be Rational* benchmark on the same random grid.

Table 1: Speed and recovery-error comparison on the random delta grid. Speed is measured over 10 timing runs, each based on 1,000,000 implied-volatility evaluations per method.

|            | Speed      |        | Recovery error         |                        |                        |                        |
|------------|------------|--------|------------------------|------------------------|------------------------|------------------------|
|            | [ns/eval.] |        | [abs.]                 |                        | [rel.]                 |                        |
|            | median     | max    | median                 | max                    | median                 | max                    |
| Explicit   | 59.49      | 63.16  | $1.39 \times 10^{-16}$ | $1.33 \times 10^{-15}$ | $1.59 \times 10^{-16}$ | $4.23 \times 10^{-14}$ |
| Jäckel LBR | 180.03     | 182.78 | $1.67 \times 10^{-16}$ | $1.55 \times 10^{-15}$ | $1.68 \times 10^{-16}$ | $2.68 \times 10^{-14}$ |

To complement the randomized experiment, I also report a deterministic fixed-grid check focused on tail accuracy. Total volatility is set to  $v \in \{0.01, 0.05, 0.10, \dots, 2.00\}$  and call delta is restricted to the tail and near-tail levels  $\Delta \in \{0.01, 0.05, 0.10, 0.90, 0.95, 0.99\}$ , giving 246 fixed-grid test cases. This grid is intentionally edge-focused, its role is to confirm that the explicit formula retains its accuracy in the low- and high-delta regions. On this tail-accuracy grid, the explicit formula attains a median absolute recovery error of  $2.22 \times 10^{-16}$  and a maximum relative error of  $2.43 \times 10^{-14}$ , while LBR attains a median absolute recovery error of  $2.20 \times 10^{-16}$  and a maximum relative error of  $2.32 \times 10^{-14}$ . The two methods are

<!-- page 13 -->

essentially indistinguishable on this grid, confirming that both achieve near double-precision accuracy at the tails.

## 5 Conclusion

This paper shows that Black–Scholes implied volatility admits an exact quantile representation in variance space. The normalized option price is a probability under an inverse Gaussian law, and inverting this identity gives implied volatility — equivalently, total implied variance — as the corresponding distributional quantile. The inverse Black–Scholes map thereby acquires a direct probabilistic meaning, and implied volatility becomes a distributional transform of the option price on a moneyness-specific variance scale.

The representation shifts the computational task from inverting the Black–Scholes formula to evaluating a specified quantile function with more favorable conditioning. In the numerical experiment, the formula recovers implied volatility to machine precision faster than Jäckel (2024)’s reference implementation on the benchmark considered: median absolute recovery errors of  $1.39 \times 10^{-16}$  versus  $1.67 \times 10^{-16}$ , at median evaluation times of 59.49 versus 180.03 nanoseconds. The speed difference reflects the implementation structure. Like LBR, the method starts from an optimized seed, but a single Halley refinement in variance replaces two higher-order refinement steps in volatility. The benchmark is not a universal ranking of algorithms, but it demonstrates that the quantile formula is not only analytic but numerically practical.

The same variance-space law also organizes objects usually treated separately. Variance-vega is the generalized inverse Gaussian density, and the higher variance and moneyness sensitivities are obtained by weighting this density. The static no-arbitrage restrictions sit on the same derivative hierarchy. Calendar spreads become probability bands in variance space, while butterfly no-arbitrage combines the variance-space Greeks with the slope and curvature of the implied-variance smile. The contribution is therefore not a new option-pricing model and not a change in the economic content of Black–Scholes. It is a new coordinate system in which pricing, inversion, sensitivities, and no-arbitrage restrictions are expressions of the same variance-quantile structure.

<!-- page 14 -->

## References

F. Black and M. Scholes. The pricing of options and corporate liabilities. *Journal of Political Economy*, 81:637–654, 1973.

Menachem Brenner and Marti G. Subrahmanyam. A simple formula to compute the implied standard deviation. *Financial Analysts Journal*, 44(5):80–83, 1988. doi: 10.2469/faj.v44.n5.80.

Peter Carr and Dilip B. Madan. Saddlepoint methods for option pricing. *Journal of Computational Finance*, 13(1):49–61, 2009. doi: 10.21314/JCF.2009.198.

M. Aslam Chaudhry and S. M. Zubair. Generalized incomplete gamma functions with applications. *Journal of Computational and Applied Mathematics*, 55(1):99–124, 1994. doi: 10.1016/0377-0427(94)90187-2.

M. Aslam Chaudhry, Nico M. Temme, and E. J. M. Veling. Asymptotics and closed form of a generalized incomplete gamma function. *Journal of Computational and Applied Mathematics*, 67(2):371–379, 1996. doi: 10.1016/0377-0427(95)00018-6.

R. S. Chhikara and J. L. Folks. *The Inverse Gaussian Distribution: Theory, Methodology, and Applications*. Marcel Dekker, New York, 1989.

Charles J. Corrado and Thomas W. Miller. A note on a simple, accurate formula to compute implied standard deviations. *Journal of Banking & Finance*, 20(3):595–603, 1996. doi: 10.1016/0378-4266(95)00014-3.

Z. Cui, J. Kirkby, D. Nguyen, and S. M. Taylor. A closed-form model-free implied volatility formula through delta families. *Journal of Derivatives*, 28(4):111–127, 2021. doi: 10.3905/JOD.2020.1.127.

Paul Embrechts. A property of the generalized inverse gaussian distribution with some applications. *Journal of Applied Probability*, 20(3):537–544, 1983.

P. Flajolet, S. Gerhold, and B. Salvy. On the non-holonomic character of logarithms, powers and the  $n$ th prime function. *Electronic Journal of Combinatorics*, 11(2):1–16, 2005.

<!-- page 15 -->

Kun Gao and Roger Lee. Asymptotics of implied volatility to arbitrary order. *Finance and Stochastics*, 18(2):349–392, 2014. doi: 10.1007/s00780-013-0223-6.

J. Gatheral and A. Jacquier. Arbitrage-free SVI volatility surfaces. *Quantitative Finance*, 14:59–71, 2014.

Jim Gatheral. *The Volatility Surface: A Practitioner's Guide*. Wiley Finance. John Wiley & Sons, Hoboken, NJ, 2006. ISBN 978-0-471-79251-2.

Jim Gatheral, Ivan Matić, Radoš Radoičić, and Dan Stefanica. Tighter bounds for implied volatility. *International Journal of Theoretical and Applied Finance*, 20(5):1750035, 2017. doi: 10.1142/S0219024917500352.

S. Gerhold. Can there be an explicit formula for implied volatility? *Quarterly Journal of Mathematics*, 63:423–436, 2012.

P. Jäckel. Let's be rational. *Wilmott*, 2015(75):40–53, 2015. doi: 10.1002/wilm.10395.

P. Jäckel. Let's Be Rational: Reference implementation. <http://www.jaeckel.org/LetsBeRational.7z>, 2024. Nominal revision 1520, dated 2024-02-16; accessed 2026-04-24.

B. Jørgensen. *Statistical Properties of the Generalized Inverse Gaussian Distribution*, volume 9 of *Lecture Notes in Statistics*. Springer, New York, 1982.

Roger W. Lee. The moment formula for implied volatility at extreme strikes. *Mathematical Finance*, 14(3):469–480, 2004. doi: 10.1111/j.0960-1627.2004.00200.x.

M. Li. A better approximation formula for the Black–Scholes implied volatility. *Journal of Futures Markets*, 28:327–341, 2008.

I. Matić, R. Radoičić, and D. Stefanica. A pde method for estimation of implied volatility. *Quantitative Finance*, 20(3):393–408, 2020. doi: 10.1080/14697688.2019.1675898.

Dan Stefanica and Radoš Radoičić. An explicit implied volatility formula. *International Journal of Theoretical and Applied Finance*, 20(7):1750048, 2017. doi: 10.1142/S0219024917500480.

<!-- page 16 -->

M. R. Tehranchi. Uniform bounds for black–scholes implied volatility. *SIAM Journal on Financial Mathematics*, 7(1):893–916, 2016. doi: 10.1137/14095248X.

M. R. Tehranchi. Uniform bounds for black–scholes implied volatility. *SIAM Journal on Financial Mathematics*, 7(1):893–916, 2016. doi: 10.1137/14095248X.

vollib. Blazingly fast & accurate: Option pricing, implied volatility, and greeks. <https://vollib.org/>, 2023. Accessed 2026-04-25.

vollib. Blazingly fast & accurate: Option pricing, implied volatility, and greeks. <https://vollib.org/>, 2023. Accessed 2026-04-25.

<!-- page 17 -->

# A Appendix

## A.1 Alternatives to the inverse Gaussian representation

The inverse Gaussian representation is useful not because the inverse Gaussian family is unique, but because it exposes additional analytical structure. The same Black–Scholes identity can be rewritten in several equivalent forms, each revealing a different aspect: the tilted  $\chi^2$  / generalized incomplete gamma representation connects implied volatility to classical special-function families with developed numerical and asymptotic literatures; the incomplete Bessel- $K$  representation locates the non- $D$ -finiteness of implied volatility at the truncation-and-inversion step; the tilted Levy representation exhibits the call price as a Girsanov-tilted first-passage probability of undrifted Brownian motion; and the tilted half-normal / Nakagami representation states the same identity in volatility coordinates. These representations are not independent — each is obtained from the inverse Gaussian form by an elementary change of variable — and the substantive probabilistic content sits in variance space. Throughout, I restrict attention to the OTM call branch  $k > 0$  and use  $w = \sigma^2 T$ . Sections A.1.1–A.1.3 record variance-space representations, all of which invert directly in total variance. Section A.1.4 records the corresponding volatility-space representation, obtained from these by a square-root change of variable.

### A.1.1 Tilted Chi-square / generalized incomplete gamma

The inverse Gaussian law admits an equivalent reading as an inverse-square exponentially tilted  $\chi_1^2$ , equivalently  $\Gamma(\frac{1}{2}, \frac{1}{2})$ , distribution. For  $k > 0$ , define

$$\mathcal{F}_{\chi,k}(x) := \frac{e^{k/2}}{\sqrt{2\pi}} \int_0^x \omega^{-1/2} \exp \left\{ -\frac{\omega}{2} - \frac{k^2}{8\omega} \right\} d\omega, \quad x > 0. \tag{28}$$

Then  $\mathcal{F}_{\chi,k}$  is the distribution function of a  $\chi_1^2$  law exponentially tilted by  $\exp\{-k^2/(8\omega)\}$ . Letting  $\mathcal{F}_{\chi,k}^{-1}$  denote its inverse, for  $k > 0$ ,

$$c = \mathcal{F}_{\chi,k} \left( \frac{w}{4} \right), \quad w = 4 \mathcal{F}_{\chi,k}^{-1}(c). \tag{29}$$

<!-- page 18 -->

The same object is, up to rescaling, a normalized lower generalized incomplete-gamma function of order  $1/2$  in the sense of Chaudhry and Zubair (1994); Chaudhry et al. (1996): the substitution  $\omega \mapsto \omega/2$  in the integrand yields the identity  $e^{-k/2}c = \mathcal{F}_{\Gamma,k}(w/8)$  with  $\mathcal{F}_{\Gamma,k}(x) := \pi^{-1/2} \int_0^x \omega^{-1/2} \exp\{-\omega - k^2/(16\omega)\} d\omega$ . This places the Black–Scholes inversion within the developed numerical, asymptotic, and series-expansion literature for generalized incomplete gamma functions, with the moneyness parameter  $k$  entering as the upper tilt.

### **A.1.2 Incomplete Bessel- $K$**

The modified Bessel function of the second kind admits the integral representation

$$\mathcal{B}_\alpha(z) := \frac{1}{2} \int_0^\infty \omega^{\alpha-1} \exp \left\{ -\frac{z}{2} \left( \omega + \frac{1}{\omega} \right) \right\} d\omega, \quad z > 0, \tag{30}$$

with lower incomplete version obtained by truncating the upper limit,

$$\mathcal{B}_{\alpha,z}(x) := \frac{1}{2} \int_0^x \omega^{\alpha-1} \exp \left\{ -\frac{z}{2} \left( \omega + \frac{1}{\omega} \right) \right\} d\omega, \quad x > 0. \tag{31}$$

Letting  $\mathcal{B}_{\alpha,z}^{-1}$  denote the inverse in  $x$ , for  $k > 0$ ,

$$c \mathcal{B}_{1/2} \left( \frac{k}{2} \right) = \mathcal{B}_{1/2,k/2} \left( \frac{w}{2k} \right), \quad w = 2k \mathcal{B}_{1/2,k/2}^{-1} \left( c \mathcal{B}_{1/2} \left( \frac{k}{2} \right) \right). \tag{32}$$

This representation is analytically informative for the non- $D$ -finiteness question. The untruncated Bessel- $K_{1/2}$  is itself  $D$ -finite, and so is the integrand of  $\mathcal{B}_{1/2,k/2}$ ; non- $D$ -finiteness of implied volatility therefore cannot enter through the integrand but must enter through the combination of finite truncation and functional inversion. The representation thus locates the obstruction identified in Appendix A.2 at a specific operation rather than at the underlying special function.

<!-- page 19 -->

### A.1.3 Tilted Levy

The inverse Gaussian law can also be viewed as an exponentially tilted Levy law. For  $k > 0$ , define

$$\mathcal{F}_{\ell,k}(x) := \frac{e^{k/2}}{\sqrt{2\pi}} \int_0^x \omega^{-3/2} \exp \left\{ -\frac{1}{2\omega} - \frac{k^2\omega}{8} \right\} d\omega, \quad x > 0. \tag{33}$$

This is the distribution function of a Levy law exponentially tilted by  $\exp\{-k^2\omega/8\}$ . Letting  $\mathcal{F}_{\ell,k}^{-1}$  denote its inverse, for  $k > 0$ ,

$$c = 1 - \mathcal{F}_{\ell,k} \left( \frac{4}{w} \right), \quad w = \frac{4}{\mathcal{F}_{\ell,k}^{-1}(1-c)}. \tag{34}$$

This representation has a clean probabilistic reading. The Levy distribution is the law of the first-passage time of standard Brownian motion without drift to a fixed level. The exponential tilt  $\exp\{-k^2\omega/8\}$  is the Radon–Nikodym density that, under Girsanov’s theorem, introduces the drift  $k/2$ . The normalized Black–Scholes call price is therefore a Girsanov-tilted first-passage probability for undrifted Brownian motion, complementing the drifted first-passage reading from the inverse Gaussian form in Section 3.1.

#### A.1.4 Tilted half-normal / Nakagami

The previous representations all invert in total variance  $w$ . Applying the square-root change of variable to the tilted  $\chi^2$  representation in Section A.1.1 yields an equivalent representation in total volatility  $v = \sqrt{w}$ . The square root of a  $\Gamma(\frac{1}{2}, \frac{1}{2})$  variable follows the standard half-normal law, equivalently a Nakagami distribution with shape parameter  $1/2$  and spread parameter  $1$ . For  $k > 0$ , define

$$\mathcal{F}_{N,k}(x) := e^{k/2} \sqrt{\frac{2}{\pi}} \int_0^x \exp \left\{ -\frac{\nu^2}{2} - \frac{k^2}{8\nu^2} \right\} d\nu, \quad x > 0. \tag{35}$$

Then  $\mathcal{F}_{N,k}$  is the distribution function of a standard half-normal, or Nakagami( $\frac{1}{2}$ , 1), law exponentially tilted by  $\exp\{-k^2/(8\nu^2)\}$ , and for  $k > 0$ ,

$$c = \mathcal{F}_{N,k} \left( \frac{v}{2} \right), \quad w = 4 \left( \mathcal{F}_{N,k}^{-1}(c) \right)^2, \quad v = 2 \mathcal{F}_{N,k}^{-1}(c). \tag{36}$$

<!-- page 20 -->

The implied total volatility is thus obtainable from a direct distributional transform. However, the tilt term  $k^2/(8\nu^2)$  is itself a function of inverse variance, so the construction still carries the variance-space structure even when stated in volatility coordinates. This volatility quantile is therefore best read as a square-root projection of the variance-space probabilistic law rather than as an independent representation. This is consistent with the numerical observation in Section 4 that the inverse is more stable in variance than in volatility, with the  $1/(2\nu)$  factor in the volatility-space inverse sensitivity being the differential analogue of the same square-root projection.

## A.2 The Quantile is not D-finite

**Proposition 1.** *Fix  $k > 0$  and define*

$$w(c) := \mathcal{F}_{GIG}^{-1}\left(c; \frac{1}{2}, \frac{1}{4}, k^2\right), \quad 0 < c < 1.$$

*Proof.* For  $Z_k \sim GIG(\frac{1}{2}, \frac{1}{4}, k^2)$  the density is

*Then  $w$  is not  $D$ -finite as a function of  $c$ .*

$$f_k(w) = \frac{e^{k/2}}{2\sqrt{2\pi}} w^{-1/2} \exp\left(-\frac{w}{8} - \frac{k^2}{2w}\right), \quad w > 0. \tag{37}$$

*Step 1: small-w asymptotic of the cdf.* As  $w \downarrow 0$ , the factor  $e^{-x/8} \rightarrow 1$  uniformly on  $[0, w]$ , so

$$\begin{aligned}\mathcal{F}_{GIG,k}(w) &= \frac{e^{k/2}}{2\sqrt{2\pi}} \int_0^w x^{-1/2} \exp\left(-\frac{x}{8} - \frac{k^2}{2x}\right) dx \\ &\sim \frac{e^{k/2}}{2\sqrt{2\pi}} \int_0^w x^{-1/2} \exp\left(-\frac{k^2}{2x}\right) dx.\end{aligned} \tag{38}$$

Substituting  $u = k^2/(2x)$  yields

$$\int_0^w x^{-1/2} \exp\left(-\frac{k^2}{2x}\right) dx = \frac{k}{\sqrt{2}} \int_{k^2/(2w)}^\infty u^{-3/2} e^{-u} du \sim \frac{2w^{3/2}}{k^2} e^{-k^2/(2w)},$$

where the last step uses the standard tail expansion  $\int_A^\infty u^{-3/2} e^{-u} du \sim A^{-3/2} e^{-A}$  as  $A \rightarrow \infty$ .

<!-- page 21 -->

Hence

$$\mathcal{F}_{GIG,k}(w) \sim \frac{e^{k/2}}{k^2 \sqrt{2\pi}} w^{3/2} \exp\left(-\frac{k^2}{2w}\right), \quad w \downarrow 0. \tag{39}$$

*Step 2: inversion by bootstrap.* Set  $c = \mathcal{F}_{GIG,k}(w)$ . Taking logarithms in (39) gives

$$\log \frac{1}{c} = \frac{k^2}{2w} - \frac{3}{2} \log w + \log \left( \frac{k^2 \sqrt{2\pi}}{e^{k/2}} \right) + o(1), \quad w \downarrow 0. \tag{40}$$

A first-pass estimate ignoring all but the leading term yields  $w \approx k^2/(2\log(1/c))$ , so

$$\log w \sim -\log \log(1/c), \quad c \downarrow 0,$$

which is  $O(\log \log(1/c))$ . Substituting back into (40),

$$\log \frac{1}{c} = \frac{k^2}{2w} + O\left(\log \log \frac{1}{c}\right),$$

and solving for  $w$ ,

$$w(c) = \frac{k^2}{2 \log(1/c)} \left( 1 + O\left( \frac{\log \log(1/c)}{\log(1/c)} \right) \right), \quad c \downarrow 0. \tag{41}$$

*Step 3: incompatibility with  $D$ -finiteness.* A univariate  $D$ -finite function admits, at each finite singularity, an asymptotic expansion whose building blocks are products of  $(c - c_0)^\alpha$  for  $\alpha \in \mathbb{C}$ , exponentials  $\exp(P((c - c_0)^{-1/r}))$  for some polynomial  $P$  and integer  $r \geq 1$ , and *nonnegative integer* powers of  $\log(c - c_0)$ ; see (Flajolet et al., 2005, Thm. 1). The asymptotic (41) contains the factor  $(\log(1/c))^{-1}$ , a reciprocal logarithmic power, which is incompatible with this structure. Hence  $w$  is not  $D$ -finite.  $\square$

In particular,  $w(c) \sim k^2/(2 \log(1/c))$  as  $c \downarrow 0$ .

**Corollary 1.** Fix  $T > 0$ ,  $k > 0$ . The implied-volatility map  $c \mapsto \sigma(k, c)$  on  $(0, 1)$  is not  $D$ -finite. The joint map  $(k, c) \mapsto \sigma(k, c)$  on the OTM region  $\{k > 0, 0 < c < 1\}$  is not  $D$ -finite either.

*Proof.* If  $\sigma(k, \cdot)$  were  $D$ -finite at fixed  $k$ , then so would be  $w(c) = T\sigma(k, c)^2$  by closure of the  $D$ -finite class under products and scalar multiplication, contradicting Proposition 1. If

<!-- page 22 -->

the joint map were  $D$ -finite, specialization to any fixed  $k > 0$  would yield a  $D$ -finite function of  $c$  alone, again contradicting Proposition 1.  $\square$

**Remark 1** (Boundary cases). *The case  $k = 0$  admits the closed-form solution  $\sigma = (2/\sqrt{T}) \Phi^{-1}((1+c)/2)$  and is excluded from the present argument. The ITM call and put cases reduce to the OTM call case treated above by the parity transformations of Section 2, so the non-D-finiteness conclusion extends to all four branches.*

**Remark 2** (Relation to Gerhold (2012)). *Gerhold (2012) established non- $D$ -finiteness of implied volatility through a univariate specialization  $S = eK$ ,  $c = (e - 1)K + eK^2$ , recovering the obstruction  $F^{-1}(x) \sim 1/\sqrt{2 \log(1/x)}$  as  $x \downarrow 0$ . The variance-quantile representation makes the same obstruction transparent at every fixed log-moneyness  $k > 0$ : the inverse Gaussian tail produces, via (39)–(41), a reciprocal-logarithmic asymptotic of the same forbidden type. The present proof therefore confirms and slightly sharpens Gerhold (2012), in that the obstruction is identified pointwise in  $k$  rather than only along a one-dimensional curve in  $(S, K, c)$ -space.*
