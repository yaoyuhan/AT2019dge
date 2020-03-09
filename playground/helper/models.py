#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 12 13:25:30 2020

@author: yuhanyao
"""
import os
import sys
sys.path.append("/scratch/yyao/AT2019dge/playground/")
import time
import numpy as np
from helper import phys
from helper.mcmcfit import planck_lambda
from multiprocessing import Pool
import emcee
import matplotlib.pyplot as plt
import corner
fs = 14
    
##### interaction: Piro and Nakar model
def model_piro15_bol(t_, Renv=1e+13, Menv_=0.01, E51=0.5, Mcore_=4):
    t = t_ * 24*3600 #  in seconds
    
    Menv_001 = Menv_ / 0.01
    
    v_e = 1.5e+9 * E51**0.5 * (Mcore_/3)**(-0.35) * Menv_001**(-0.15) # Nakar & Piro 2014, Eq (8)
    t_e = Renv / v_e
    E_e = 4e+49 * E51 * Mcore_**(-0.7) * Menv_001**(0.7) # Piro 2015 Eq (3)
    
    kappa = 0.2
    t_p = 0.9 * (kappa/0.34)**0.5 * E51**(-1/4) * Mcore_**0.17 * Menv_001**0.57 * (3600 * 24)  
    # Piro 2015 Eq (6), convert day to seconds
    L = t_e * E_e / t_p**2 * np.exp(- t * (t + 2*t_e) / (2*t_p**2)) # Piro 2015 Eq (15)
    # R = v_e * t + Renv # Piro 2015 Eq (8)
    # sigmaT4 = L / (4 * np.pi * R **2)
    # T = (sigmaT4/phys.sigma)**(1/4.)
    return L



def model_piro15(t_, wv, Renv=1e+13, Menv_=0.01, E51=0.5, Mcore_=4):
    """
    wv in angstrom
    t_ in day
    Renv in cm
    Menv_ in Msun
    Mcore_ in Msun
    
    Give time since explosion (in day)
    wavelength (in AA)
    predict Llambda
    """
    t = t_ * 24*3600 #  in seconds
    #Menv = Menv_ * phys.sm
    
    #E51 = 0.5 # 1 * phys.sm * (9000*1e+5)**2 * 0.3 / 1e+51
    #Mcore_ = 4
    Menv_001 = Menv_ / 0.01
    
    v_e = 2e+9 * E51**0.5 * Mcore_**(-0.35) * Menv_001**(-0.15) # Piro 2015, Eq (2)
    t_e = Renv / v_e
    E_e = 4e+49 * E51 * Mcore_**(-0.7) * Menv_001**(0.7) # Piro 2015 Eq (3)
    
    kappa = 0.2
    
    t_p = 0.9 * (kappa/0.34)**0.5 * E51**(-1/4) * Mcore_**0.17 * Menv_001**0.57 * (3600 * 24)  
    # Piro 2015 Eq (6), convert day to seconds
    
    L = t_e * E_e / t_p**2 * np.exp(- t * (t + 2*t_e) / (2*t_p**2)) # Piro 2015 Eq (15)
    R = v_e * t + Renv # Piro 2015 Eq (8)
    
    sigmaT4 = L / (4 * np.pi * R **2)
    T = (sigmaT4/phys.sigma)**(1/4.)
    Llambda = planck_lambda(T, R/phys.sr, wv)
    ix = t<0
    Llambda[ix] = 0
    return Llambda


def piro15_lnlike(theta, tt, wv, lgL, lgL_unc):
    """
    taum_, Mni_, texp_ are in the unit of day, Msun, day
    """
    lgRenv, lgMenv_, texp, E51, Mcore_ = theta
    Renv = 10**lgRenv
    Menv_ = 10**lgMenv_
    t_ = tt - texp
    model = model_piro15(t_, wv, Renv, Menv_, E51, Mcore_)
    lgmodel = np.log10(model)
    
    chi2_term = -1/2*np.sum((lgL - lgmodel)**2/lgL_unc**2)
    error_term = np.sum(np.log(1/np.sqrt(2*np.pi*lgL_unc**2)))
    
    ln_l = chi2_term + error_term
    return ln_l

piro15_nll = lambda *args: -piro15_lnlike(*args)


def piro15_lnprior(theta):
    lgRenv, lgMenv_, texp, E51, Mcore_ = theta
    if ((5 < lgRenv < 25) and (-4 < lgMenv_ < 0) and (-8 < texp < -2.76) and (0.01 < E51 < 10) and (0.1 < Mcore_ < 50)):
        return 0.0
    return -np.inf

def piro15_lnprob(theta, x, wv, y, yerr):
    lp = piro15_lnprior(theta)
    if not np.isfinite(lp):
        return -np.inf
    return lp + piro15_lnlike(theta, x, wv, y, yerr)


def makeCornerP15(sampler, nburn, paramsNames, quantiles=[0.16, 0.5, 0.84]):
    samples = sampler.get_chain(discard=nburn, flat=True)
    corner.corner(samples, labels = paramsNames, quantiles = quantiles, 
                  range = [0.975, 0.99, 0.975, 0.999, 0.999],
                  show_titles=True, plot_datapoints=False, 
                  title_kwargs = {"fontsize": fs})
    
#define function to plot walker chains  
def plotChains(sampler, nburn, paramsNames, nplot):
    Nparams = len(paramsNames)
    fig, ax = plt.subplots(Nparams+1, 1, figsize = (8,2*(Nparams+1)), sharex = True)
    fig.subplots_adjust(hspace = 0)
    ax[0].set_title('Chains', fontsize=fs)
    xplot = np.arange(sampler.get_chain().shape[0])

    selected_walkers = np.random.choice(range(sampler.get_chain().shape[1]), nplot, replace=False)
    for i,p in enumerate(paramsNames):
        for w in selected_walkers:
            burn = ax[i].plot(xplot[:nburn], sampler.get_chain()[:nburn,w,i], 
                              alpha = 0.4, lw = 0.7, zorder = 1)
            ax[i].plot(xplot[nburn:], sampler.get_chain(discard=nburn)[:,w,i], 
                       color=burn[0].get_color(), alpha = 0.8, lw = 0.7, zorder = 1)
            
            ax[i].set_ylabel(p)
            if i==Nparams-1:
                ax[i+1].plot(xplot[:nburn], sampler.get_log_prob()[:nburn,w], 
                             color=burn[0].get_color(), alpha = 0.4, lw = 0.7, zorder = 1)
                ax[i+1].plot(xplot[nburn:], sampler.get_log_prob(discard=nburn)[:,w], 
                             color=burn[0].get_color(), alpha = 0.8, lw = 0.7, zorder = 1)
                ax[i+1].set_ylabel('ln P')
            
    return ax



def plotSED(tt, wv, lgL, lgL_unc, filename):
    
    reader = emcee.backends.HDFBackend(filename)
    
    samples = reader.get_chain(discard=250, flat=True)
    
    lgR_sigmas = np.percentile(samples[:,0], (0.13, 2.27, 15.87, 50, 84.13, 97.73, 99.87))
    lgM_sigmas = np.percentile(samples[:,1], (0.13, 2.27, 15.87, 50, 84.13, 97.73, 99.87))
    t0_sigmas = np.percentile(samples[:,2], (0.13, 2.27, 15.87, 50, 84.13, 97.73, 99.87))
    E51_sigmas = np.percentile(samples[:,3], (0.13, 2.27, 15.87, 50, 84.13, 97.73, 99.87))
    Mcore_sigmas = np.percentile(samples[:,4], (0.13, 2.27, 15.87, 50, 84.13, 97.73, 99.87))
    
    Renv = 10**lgR_sigmas[3]
    Menv_ = 10**lgM_sigmas[3]
    t0 = t0_sigmas[3]
    E51 = E51_sigmas[3]
    Mcore_ = Mcore_sigmas[3]
    
    plt.figure(figsize=(6,6))
    wvs = np.array([2079. , 2255.1, 2614.2, 3475.5, 4359.1, 4800. , 5430.1, 6300. , 7800. , 9670. ])
    names = np.array(["$UVW2$", "$UVM2$", "$UVW1$", "$U$", "$B$", "$g$", "$V$", "$r$", "$i$", "$z$"])
    colors = np.array(["k", "navy", "b", "indigo", "blueviolet", "royalblue", "darkcyan", "crimson", "gold", "pink"])
    tgrid = np.linspace(0, 10, 100)
    for i in range(len(wvs)):
        wave = wvs[i]
        color = colors[i]
        name = names[i]
        ix = wv == wave
        plt.errorbar(tt[ix]-t0, lgL[ix], lgL_unc[ix], fmt="o-", color = color)
        mymodel = model_piro15(tgrid, wv=wave, Renv=Renv, Menv_=Menv_, E51 = E51, Mcore_ = Mcore_)
        lgLmodel = np.log10(mymodel)
        plt.plot(tgrid, lgLmodel, color = color, label = name)
    plt.ylim(36, 39.3)
    plt.xlim(-1, 10)
    plt.legend(ncol = 3, frameon = False)
    plt.xlabel("Time Since Explosion (day)")
    plt.ylabel(r'$L_{\lambda}$ log'+r'$_{10}\rm(erg\,s^{-1}\,\AA^{-1})$')
    plt.tight_layout()
    

def submcmcfit(tcut, tt, wv, lgL, lgL_unc):
    print ("")
    print ("================================")
    print ("=====  tcut = %.1f day  ========="%tcut)
    dirpath = "./piromodel/%.1f/"%tcut
    if not os.path.isdir(dirpath):
        os.mkdir(dirpath)
        
    ix = tt < tcut
    tt = tt[ix]
    wv = wv[ix]
    lgL = lgL[ix]
    lgL_unc = lgL_unc[ix]
    
       
    nwalkers = 100
    ml_guess = np.array([13., -1, -4.3, 3, 10])
    #initial position of walkers
    ndim = len(ml_guess)
    nfac = [1e-3]*ndim
    pos = [ml_guess + nfac * np.random.randn(ndim) for i in range(nwalkers)]
    
    max_samples = 20000
    check_tau = 200
    
    filename = dirpath + "sampler.h5"
    if os.path.isfile(filename):
        os.remove(filename)
    backend = emcee.backends.HDFBackend(filename)
    backend.reset(nwalkers, ndim)
    
    with Pool(20) as pool:
        sampler = emcee.EnsembleSampler(nwalkers, ndim, piro15_lnprob, 
                                        args=(tt, wv, lgL, lgL_unc),
                                        pool=pool, backend=backend)
        index = 0
        autocorr = np.empty(max_samples)
        old_tau = np.inf
        for sample in sampler.sample(pos, iterations=max_samples, progress=True):
            # Only check convergence every 30 steps
            if sampler.iteration % check_tau:
                continue
            
            tstart = time.time()
            tau = sampler.get_autocorr_time(tol=0)
            tend = time.time()
            autocorr[index] = np.mean(tau[:3]) # only expect the first three parameters to converge
            index += 1
            steps_so_far = index*check_tau
            """
            print('''After {:d} steps, 
                  autocorrelation takes {:.3f} s ({} total FFTs)                
                  acceptance fraction = {:.4f}, and
                  tau = {}'''.format(steps_so_far, 
                                     tend-tstart, nwalkers*ndim,
                                     np.mean(sampler.acceptance_fraction), 
                                     tau))
            """
            # Check convergence
            converged = np.all(tau * 100 < sampler.iteration)
            converged &= np.all(np.abs(old_tau - tau) / tau < 0.01)
            if converged:
                break
            old_tau = tau
            
    print ("")
    print ("****** converged? ******")
    print (converged)
    
    paramsNames=['lg' +r'$R_\mathrm{env}$', 
                    'lg' +r'$M_\mathrm{env}$', 
                    r"$t_0$",
                    "E51", 
                    r"$M_{\rm core}$"]

    plotChains(sampler, 25, paramsNames, nplot=35)
    plt.tight_layout()
    plt.savefig(dirpath+"chains.pdf")
    
    makeCornerP15(sampler, 25, paramsNames)
    plt.savefig(dirpath+"corner.pdf")
    
    plotSED(tt, wv, lgL, lgL_unc, filename)
    plt.savefig(dirpath+"sed_model.pdf")
    


if __name__ == "__main__":
#def main_shockmodel():
   
    tt = np.array([-2.7579, -2.7158, -1.7692, -1.7193, -1.6837, -1.0456, -1.0448,
       -1.0425, -1.0417, -0.7604, -0.7484, -0.3739, -0.372 , -0.3711,
       -0.3701, -0.3663, -0.3654, -0.0363, -0.0355,  0.2082,  0.3747,
        0.3766,  0.3775,  0.3785,  0.3823,  0.3833,  1.0324,  1.0332,
        1.0355,  1.0363,  1.2009,  1.2691,  2.2191,  3.2101,  3.248 ,
        3.3159,  4.2222,  4.2658,  5.23  ,  5.2794,  6.1489,  6.8252,
        6.826 ,  6.8268,  6.8277,  7.8676,  7.8685,  7.8693,  7.8701,
        8.174 ,  8.2525,  8.8472,  8.8472,  8.8489,  8.8497,  9.188 ,
        9.2784,  9.9109,  9.9117,  9.9125, 10.2315, 10.2841, 10.9142,
       10.915 , 10.9158, 10.9167, 11.8926, 11.8935, 11.8943, 11.8951,
       12.938 , 12.9388, 12.9396, 12.9405, 13.1822, 13.1929, 13.2781,
       13.9508, 13.9516, 13.9539, 13.9547, 14.205 , 14.2728, 14.9207,
       14.9218, 14.9247, 14.9257, 15.161 , 15.9894, 15.9918, 16.0766,
       16.2846, 17.2715, 17.9606])
        
    wv = np.array([4800. , 6300. , 6300. , 4800. , 7800. , 4800. , 6300. , 7800. ,
       9670. , 4800. , 6300. , 2614.2, 3475.5, 4359.1, 2079. , 5430.1,
       2255.1, 4800. , 6300. , 4800. , 2614.2, 3475.5, 4359.1, 2079. ,
       5430.1, 2255.1, 4800. , 6300. , 7800. , 9670. , 6300. , 4800. ,
       6300. , 6300. , 4800. , 7800. , 6300. , 4800. , 6300. , 4800. ,
       6300. , 4800. , 6300. , 7800. , 9670. , 4800. , 6300. , 7800. ,
       9670. , 4800. , 6300. , 6300. , 4800. , 7800. , 9670. , 6300. ,
       4800. , 6300. , 7800. , 9670. , 6300. , 4800. , 4800. , 6300. ,
       7800. , 9670. , 4800. , 6300. , 7800. , 9670. , 4800. , 6300. ,
       7800. , 9670. , 7800. , 6300. , 4800. , 4800. , 6300. , 7800. ,
       9670. , 6300. , 4800. , 4800. , 6300. , 7800. , 9670. , 6300. ,
       4800. , 9670. , 4800. , 6300. , 6300. , 7800. ])
        
    lgL = np.array([37.38458251, 37.10101445, 37.78101445, 38.19258251, 37.49679369,
       38.28409072, 37.95428467, 37.65479501, 37.37822288, 38.31658251,
       37.95301445, 38.82898039, 38.49098019, 38.33517392, 39.02571674,
       38.29146464, 39.00520932, 38.32809072, 38.03828467, 38.30858251,
       38.87698039, 38.32298019, 38.42317392, 38.94971674, 38.20346464,
       38.88520932, 38.28809072, 38.01828467, 37.75879501, 37.43022288,
       37.98101445, 38.25658251, 37.95701445, 37.88901445, 38.10058251,
       37.68079369, 37.84901445, 38.04458251, 37.81701445, 37.96058251,
       37.86101445, 37.93209072, 37.82628467, 37.60279501, 37.37822288,
       37.94409072, 37.76628467, 37.61079501, 37.45022288, 37.84458251,
       37.73301445, 37.78628467, 37.96009072, 37.59079501, 37.35822288,
       37.67301445, 37.91658251, 37.72628467, 37.53479501, 37.30622288,
       37.68101445, 37.80458251, 37.84409072, 37.69028467, 37.50679501,
       37.28222288, 37.79209072, 37.65028467, 37.51879501, 37.27022288,
       37.68009072, 37.59028467, 37.43479501, 37.20622288, 37.40879369,
       37.58501445, 37.67258251, 37.67209072, 37.58228467, 37.42279501,
       37.11022288, 37.51701445, 37.50458251, 37.57209072, 37.53428467,
       37.40679501, 37.03822288, 37.47301445, 37.55209072, 37.02222288,
       37.52858251, 37.46901445, 37.42501445, 37.14679501])
        
    lgL_unc = np.array([0.06 , 0.056, 0.02 , 0.012, 0.068, 0.004, 0.008, 0.008, 0.028,
       0.008, 0.008, 0.076, 0.04 , 0.16 , 0.044, 0.044, 0.028, 0.008,
       0.004, 0.016, 0.056, 0.04 , 0.116, 0.04 , 0.044, 0.036, 0.004,
       0.008, 0.008, 0.028, 0.008, 0.008, 0.012, 0.012, 0.008, 0.032,
       0.02 , 0.012, 0.012, 0.016, 0.08 , 0.056, 0.016, 0.028, 0.084,
       0.028, 0.036, 0.024, 0.048, 0.06 , 0.02 , 0.048, 0.052, 0.04 ,
       0.068, 0.052, 0.04 , 0.024, 0.032, 0.048, 0.024, 0.068, 0.08 ,
       0.032, 0.032, 0.064, 0.04 , 0.028, 0.028, 0.044, 0.044, 0.024,
       0.032, 0.064, 0.064, 0.02 , 0.032, 0.028, 0.02 , 0.028, 0.06 ,
       0.024, 0.072, 0.068, 0.024, 0.032, 0.12 , 0.036, 0.032, 0.048,
       0.032, 0.024, 0.04 , 0.04 ])
        
    """
    # remove the first data point from fitting:
    ix = tt>1
    tt = tt[ix]
    wv = wv[ix]
    lgL = lgL[ix]
    lgL_unc = lgL_unc[ix]
    """
    tcut = 2.0
    
    tcuts = np.linspace(1.0, 7.0, 7)
    for i in range(len(tcuts)):
        tcut = tcuts[i]
        submcmcfit(tcut, tt, wv, lgL, lgL_unc)
    
    #submcmcfit(tcut, tt, wv, lgL, lgL_unc)
    
    