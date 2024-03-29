from cmath import nan
from logging import PlaceHolder
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource,FuncTickFormatter, Select, CustomJS, Slider, Panel, Range1d, Tabs, Button, RangeSlider, RadioButtonGroup, PointDrawTool
from bokeh.plotting import Figure, output_file, show
from bokeh.events import Tap, Pan
import numpy as np
import math
from math import exp, erfc, sqrt
from bokeh.embed import components
from scipy.stats import qmc
import os
import sys

# Setting working sirectory to current folder
os.chdir(os.path.dirname(sys.argv[0]))

# Function: Obtain gamma for Ogata and Banks (1962) solutions
def get_gamma(reac,Dis,sep_vel):
  res = sqrt(1 + 4 * reac * Dis / sep_vel**2)
  return res

# Function: Compute concentration profile in column
def getc_cont(x,c,vel,t,L1,L2,reac_l,reac_h,disp_l,disp_h):
  # To cover a range in dispersion/diffusion and reaction, latin hypercube sampling is applied
  # The independent values of the latin hypercube are found in L1 and L2
  for j in range(len(L1)):
    # Computing values associated to the latin hypercube
    r_intermed = reac_l + (reac_h-reac_l)*L1[j]
    D_intermed = disp_l + (disp_h-disp_l)*L2[j]
    H_intermed = 2*r_intermed*D_intermed/vel**2
    # Only needed, if Ogata-Banks solution is applied
    #gam_intermed = get_gamma(r_intermed,D_intermed,vel)

    for i in range(len(x)):
      if x[i] <= 0:
        c[j,i] = 1
      else: 
        # (Ogata-Banks (8.66))
        # c[j,i] = 1/2 * exp(x[i]*vel/(2*D_intermed))*(exp(-x[i]*vel*gam_intermed/(2*D_intermed))*erfc((x[i]-vel*t*gam_intermed)/sqrt(4*D_intermed*t))+exp(x[i]*vel*gam_intermed/(2*D_intermed))*erfc((x[i]+vel*t*gam_intermed)/sqrt(4*D_intermed*t)))
        # c_t[j] = c0/2 * exp(xBTC_ini*velocity_ini/(2*disp_ini))*(exp(-xBTC_ini*velocity_ini*gam_m/(2*disp_ini))*erfc((xBTC_ini-velocity_ini*PVspan[j]*porevolume*gam_m)/sqrt(4*disp_ini*PVspan[j]*porevolume))+exp(xBTC_ini*velocity_ini*gam_m/(2*disp_ini))*erfc((xBTC_ini+velocity_ini*PVspan[j]*porevolume*gam_m)/sqrt(4*disp_ini*PVspan[j]*porevolume)))
        # (Runkler 1996 (Eq. 8))
        c[j,i] = 1/2 * exp(-r_intermed*x[i]/vel) * erfc((x[i]- vel*t*(1+H_intermed))/(2*sqrt(D_intermed*t)))
  
  return c

# Initial slider parameters (min, max, step, value)
# !Note! The following slider + disp and reac have log(values) for bokeh visualization
# To work with them use, e.g. exp(pore_vol[0])
# Pore Volume [-]
pore_vol  = [np.log(0.001), np.log(10), (np.log(10)-np.log(0.001)) / 1000, np.log(0.5)]
# Column radius [m]
col_rad   = [0.005, 0.2, 0.0001, 0.05]
# Flow rate [ml/h]
flow      = [1, 50, 0.1, 10]
# Porosity [-]
poros     = [0.01, 1, 0.01, 0.5]
# Duration of pulse injection [s]
puls_inj  = [30, 360000, 30, 18000]
# Column length [m]
col_len   = [0.01, 0.5, 0.001, 0.2]
# Solid densitiy [kg/m3]
rho_s     = [2000, 3000, 1, 2650]
# Linear partitioning coefficient [m3/kg]
Kd        = [5e-5, 5e-3, 5e-5, 2e-3]

# number of nodes in the domain
num_n = 200

# Initial slider parameters (min, max, step, minvalue, maxvalue)
# Dispersion coefficient [ln(m2/h)]
disp      = [np.log(1e-6), np.log(1e-1), (np.log(1e-1)-np.log(1e-6))/300, np.log(1e-5), np.log(5e-5)]
# First order reaction coefficient [ln(1/h)]
reac      = [np.log(1e-4), np.log(1), (np.log(1)-np.log(1e-4))/300, np.log(1e-3), np.log(5e-3)]

# Subdividing the column into 200 equally long parts
x         = np.linspace(col_len[3]*0.005,col_len[3],num_n)
# Extending x to display boundary condition
x         = np.insert(x, 0, col_len[3]*-0.05)
# Subdividing the duration of the experiment, i.e. 10 pore volumes, into 1000 equally long parts
PVspan      = np.linspace(exp(pore_vol[0]),exp(pore_vol[1]),num_n)

# Parameters for plot initialization + adjusting units
poros_ini   = poros[3]                                      # [-]
col_len_ini = col_len[3]                                    # [m]
col_rad_ini = col_rad[3]                                    # [m]
flow_ini    = flow[3]/1000/1000/3600                        # [m3/s]     
disp_ini    = np.mean([exp(disp[3]), exp(disp[4])])/3600    # [m2/s]
reac_ini    = np.mean([exp(reac[3]), exp(reac[4])])/3600    # [1/s]

# Pore space in the column [m3]
porespace   = col_len_ini * math.pi * col_rad_ini**2 * poros_ini
# Seepage velocity [m/s]
velocity_ini    = flow_ini/(col_rad_ini**2*math.pi*poros_ini)
# Time needed to fully flush the column [s]
porevolume  = col_len_ini / velocity_ini
# Initial time point [s]
time_ini    = porevolume * exp(pore_vol[3]) 
# Intial point for breakthrough curve [m]
xBTC_ini    = col_len_ini/2
# Normed inlet concentration [-]
c0 = 1
# Area [m2]
Area =  math.pi * col_rad_ini**2 

# Latin Hypercube Sampling 
sampler = qmc.LatinHypercube(d=1)
# 2 Samples for uncertain variables with 100 values each
Lcube1 = sampler.random(100)
Lcube2 = sampler.random(100)

# Concentration list
c      = np.zeros((len(Lcube1),len(x)))
# Concentration lists for the highest and smallest concentration at each point in the column
c_mean = np.empty((1,len(x)))
c_min  = np.empty((len(x)))
c_max  = np.empty((len(x)))
c_loQ  = np.empty((len(x)))
c_upQ  = np.empty((len(x)))
# Concnetration list for breakthrough curve
c_t = np.empty((len(PVspan)))

# Solving 1D transport equation in space for 100 latin hypercube pairs
c_intermed  = getc_cont(x,c,velocity_ini,time_ini,Lcube1,Lcube2,exp(reac[3])/3600,exp(reac[4])/3600,exp(disp[3])/3600,exp(disp[4])/3600)
# Solving 1D transport equation in space for mean values
c_mean      = getc_cont(x,c_mean,velocity_ini,time_ini,[0.5],[0.5],exp(reac[3])/3600,exp(reac[4])/3600,exp(disp[3])/3600,exp(disp[4])/3600)

# Extracting min, max and quantile values from latin hypercube sample for visualization
for j in range(len(x)):
  c_min[j] = np.min(c_intermed[:,j])
  c_max[j] = np.max(c_intermed[:,j])
  c_loQ[j] = np.quantile(c_intermed[:,j],0.25)
  c_upQ[j] = np.quantile(c_intermed[:,j],0.75)

# Breaktrhough Curve: Gamma coefficient needed for Ogata-Banks solution
gam_m = get_gamma(reac_ini,disp_ini,velocity_ini)

# Breaktrhough Curve: Solving 1D transport equation in time for a given point (Ogata and Banks 1962)
for j in range(len(PVspan)):
  c_t[j] = c0/2 * exp(xBTC_ini*velocity_ini/(2*disp_ini))*(exp(-xBTC_ini*velocity_ini*gam_m/(2*disp_ini))*erfc((xBTC_ini-velocity_ini*PVspan[j]*porevolume*gam_m)/sqrt(4*disp_ini*PVspan[j]*porevolume))+exp(xBTC_ini*velocity_ini*gam_m/(2*disp_ini))*erfc((xBTC_ini+velocity_ini*PVspan[j]*porevolume*gam_m)/sqrt(4*disp_ini*PVspan[j]*porevolume)))

# Defining data sources with dictionary
source1 = ColumnDataSource(data = dict(x=x, y=c_mean[0], ymin = c_min, ymax = c_max, yloQ = c_loQ, yupQ = c_upQ))
source2 = ColumnDataSource(data = dict(x2=PVspan, y2=c_t))
source3 = ColumnDataSource(data = dict(xBTC = [col_len[3]/2], yBTC = [0]))

# Widgets for unit selection
r_us  = Select(title="Reaction Unit:",    value="1/h",  options=["1/s", "1/min", "1/h", "1/d"])
D_us  = Select(title="Dispersion Unit:",  value="m2/h", options=["m2/s", "m2/min", "m2/h", "m2/d"])
fl_us = Select(title="Flow Rate Unit:",   value="mL/h", options=["mL/min", "m3/s", "mL/h", "L/h"])

# Dictionaries for unit and value display
r_us_dict = { '1/s':    FuncTickFormatter(code="""  return (Math.exp(tick)/3600).toExponential(2).toString()+' [1/s]'"""),
              '1/min':  FuncTickFormatter(code="""  return (Math.exp(tick)/60).toExponential(2).toString()+' [1/min]'"""),
              '1/h':    FuncTickFormatter(code="""  return (Math.exp(tick)).toExponential(2).toString()+' [1/h]'"""),
              '1/d':    FuncTickFormatter(code="""  return (Math.exp(tick)*24).toExponential(2).toString()+' [1/d]'""")}

D_us_dict = { 'm2/s':    FuncTickFormatter(code="""  return (Math.exp(tick)/3600).toExponential(2).toString()+' [m2/s]'"""),
              'm2/min':  FuncTickFormatter(code="""  return (Math.exp(tick)/60).toExponential(2).toString()+' [m2/min]'"""),
              'm2/h':    FuncTickFormatter(code="""  return (Math.exp(tick)).toExponential(2).toString()+' [m2/h]'"""),
              'm2/d':    FuncTickFormatter(code="""  return (Math.exp(tick)*24).toExponential(2).toString()+' [m2/d]'""")}              

fl_us_dict = {'m3/s':     FuncTickFormatter(code="""  return (tick/3600/1000/1000).toExponential(2)+' [m3/s]'"""),
              'L/h':      FuncTickFormatter(code="""  return (tick/1000).toFixed(4)+' [L/h]'"""),
              'mL/min':   FuncTickFormatter(code="""  return (tick/60).toFixed(2)+' [mL/min]'"""),
              'mL/h':     FuncTickFormatter(code="""  return (tick).toFixed(1)+' [mL/h]'""")}

# Plot 1: Concentration within the column
COLp = Figure(min_height = 400, y_axis_label='c(t)/c0',
            x_axis_label='x [m]',sizing_mode="stretch_both")
# 5 different lines, displaying median, upper and lower quartile, lowest and highest values
COLp.line('x', 'y', source = source1, line_width = 3, line_alpha = 0.6, line_color = 'red')
COLp.line('x', 'yloQ', source = source1, line_width = 3, line_alpha = 0.6, line_color = 'black', line_dash = 'dashed', legend_label = 'lower / upper Quartile')
COLp.line('x', 'yupQ', source = source1, line_width = 3, line_alpha = 0.6, line_color = 'black', line_dash = 'dashed')
COLp.line('x', 'ymin', source = source1, line_width = 3, line_alpha = 0.6, line_color = 'grey', line_dash = 'dashed', legend_label = 'Minimum / Maximum')
COLp.line('x', 'ymax', source = source1, line_width = 3, line_alpha = 0.6, line_color = 'grey', line_dash = 'dashed')
COLp.legend.location = "top_right"
COLp.y_range = Range1d(-0.03, 1.05)
COLp.xaxis.axis_label_text_font_size = "17pt"
COLp.yaxis.axis_label_text_font_size = "17pt"
COLp.xaxis.major_label_text_font_size = "12pt"
COLp.yaxis.major_label_text_font_size = "12pt" 

# Initializing PointDrawTool --> Select location of BTC
BTCcircle = COLp.diamond(x='xBTC',y = 'yBTC', source=source3 , size=18, color = 'black', fill_alpha=0.6 )
COLp.add_tools(PointDrawTool(renderers=[BTCcircle], num_objects = 1))
COLp.toolbar.active_multi = COLp.select_one(PointDrawTool)

# Plot 2: BTC
BTCp = Figure(min_height = 400, y_axis_label='c(t)/c0',
            x_axis_label='Pore Volume',sizing_mode="stretch_both")
BTCp.line('x2', 'y2', source = source2, line_width = 3, line_alpha = 0.6, line_color = 'red')
BTCp.y_range = Range1d(0, 1.05)
BTCp.x_range = Range1d(0, exp(pore_vol[1]))
BTCp.title = "Breakthrough Curve at x = 0.100 m (Drag diamond in upper plot to change)"
BTCp.xaxis.axis_label_text_font_size = "17pt"
BTCp.yaxis.axis_label_text_font_size = "17pt"
BTCp.xaxis.major_label_text_font_size = "12pt"
BTCp.yaxis.major_label_text_font_size = "12pt" 
BTCp.title.text_font_size = "13pt"

# Sliders 
pore_vol_sl   = Slider(start=pore_vol[0], end=pore_vol[1], value=pore_vol[3], step=pore_vol[2], title="Pore Volume (1PV = " + str("%.2f" %(porevolume/3600)) + " h)",
                    format=FuncTickFormatter(code="""return (Math.exp(tick)).toFixed(4)+' [PV]'"""),sizing_mode="stretch_width")
pulse_inj_sl  = Slider(title = "Duration of Injection", start = puls_inj[0], end = puls_inj[1], step = puls_inj[2], value = puls_inj[3],
                    format=FuncTickFormatter(code="""return (tick/60).toFixed(1)+' [min]'"""),sizing_mode="stretch_width")
col_len_sl    = Slider(title = "Column length", start = col_len[0], end = col_len[1], step = col_len[2], value = col_len[3],
                    format=FuncTickFormatter(code="""return tick.toFixed(3)+' [m]'"""),sizing_mode="stretch_width")
col_rad_sl    = Slider(title = "Column radius", start = col_rad[0], end = col_rad[1], step = col_rad[2], value = col_rad[3],
                    format=FuncTickFormatter(code="""return tick.toFixed(3)+' [m]'"""),sizing_mode="stretch_width")
disp_sl       = RangeSlider(title = "Dispersion coefficient ", start = disp[0], end = disp[1], step = disp[2], value =(disp[3], disp[4]),
                    format=D_us_dict['m2/h'],sizing_mode="stretch_width")
reac_sl       = RangeSlider(title = "Reaction coefficient ", start = reac[0], end = reac[1], step = reac[2], value = (reac[3], reac[4]),
                    format=r_us_dict['1/h'],sizing_mode="stretch_width")
flow_sl       = Slider(title = "Flow Rate", start = flow[0], end = flow[1], step = flow[2], value = flow[3],
                    format=fl_us_dict['mL/h'] ,sizing_mode="stretch_width")
poros_sl      = Slider(title = "Porosity", start = poros[0], end = poros[1], step = poros[2], value = poros[3],
                    format=FuncTickFormatter(code="""return tick.toFixed(2)+' [-]'"""),sizing_mode="stretch_width")
# Sliders for linear sorption 
rho_s_sl      = Slider(title = "Solid Density", start = rho_s[0], end = rho_s[1], step = rho_s[2], value = rho_s[3],
                    format=FuncTickFormatter(code="""return (tick/1000).toFixed(2)+' [kg/L]'"""),sizing_mode="stretch_width")
Kd_sl         = Slider(title = "Linear Partinioning Coefficient", start = Kd[0], end = Kd[1], step = Kd[2], value = Kd[3],
                    format=FuncTickFormatter(code="""return (tick*1000).toFixed(2)+' [L/kg]'"""),sizing_mode="stretch_width")

# 2 options to choose between continuous and pulse injection, as well as linear and no sorption
Labels1 = ["Continuous Injection", "Pulse Injection"]
Labels2 = ["No Sorption","Linear Sorption"]

rg_CP = RadioButtonGroup(labels = Labels1, active = 0)
rg_ST = RadioButtonGroup(labels = Labels2, active = 0)

# Accessing JavaScript code, see file callback.js
with open ('callback.js', 'r') as file1:
  cbCode = file1.read()
# Callback for interactive code via JS
callback = CustomJS(args=dict(
                            source1=source1,
                            source2 = source2,
                            source3 = source3,
                            Lcube1 = Lcube1,
                            Lcube2 = Lcube2,
                            pore_vol_sl = pore_vol_sl,
                            col_len_sl = col_len_sl,
                            reac_sl = reac_sl,
                            disp_sl = disp_sl,
                            col_rad_sl = col_rad_sl,
                            flow_sl = flow_sl,
                            poros_sl = poros_sl,
                            rho_s_sl = rho_s_sl,
                            Kd_sl = Kd_sl,
                            rg_CP = rg_CP,
                            rg_ST = rg_ST,
                            r_us = r_us,
                            D_us = D_us,
                            fl_us = fl_us,
                            r_dict = r_us_dict,
                            D_dict = D_us_dict,
                            fl_dict = fl_us_dict,
                            pulse_inj_sl = pulse_inj_sl,
                            BTCp = BTCp,
                            ),
    code=cbCode)

# Buttons to save the numeric data, displayed in plots
savebutton1 = Button(label="Save (Upper Plot)", button_type="success",sizing_mode="stretch_width")
savebutton1.js_on_click(CustomJS(args=dict(source=source1),code=open(os.path.join(os.path.dirname(__file__),"download.js")).read()))
savebutton2 = Button(label="Save (Lower Plot)", button_type="success",sizing_mode="stretch_width")
savebutton2.js_on_click(CustomJS(args=dict(source=source2),code=open(os.path.join(os.path.dirname(__file__),"download.js")).read()))
# Credit: https://stackoverflow.com/questions/31824124/is-there-a-way-to-save-bokeh-data-table-content

# Callbacks for widgets
pore_vol_sl.js_on_change('value', callback)
col_len_sl.js_on_change('value', callback)
col_rad_sl.js_on_change('value', callback)
reac_sl.js_on_change('value', callback)
disp_sl.js_on_change('value', callback)
flow_sl.js_on_change('value', callback)
poros_sl.js_on_change('value', callback)
pulse_inj_sl.js_on_change('value', callback)
Kd_sl.js_on_change('value', callback)
rho_s_sl.js_on_change('value', callback)
r_us.js_on_event(Tap, callback)
D_us.js_on_event(Tap, callback)
fl_us.js_on_event(Tap, callback)
r_us.js_on_event('value', callback)
D_us.js_on_event('value', callback)
fl_us.js_on_event('value', callback)
rg_CP.js_on_change('active',callback)
rg_ST.js_on_change('active',callback)
COLp.js_on_event(Tap, callback)
COLp.js_on_event(Pan, callback)

# Layout of the page
layout1 = column(rg_CP,rg_ST,pore_vol_sl,col_len_sl,col_rad_sl,reac_sl,disp_sl,flow_sl,poros_sl,pulse_inj_sl,rho_s_sl,Kd_sl,sizing_mode="stretch_width")
layout2 = column(r_us,D_us,fl_us,savebutton1, savebutton2, sizing_mode="stretch_width")
tab1 = Panel(child=COLp, title="ADRE")
plots = Tabs(tabs=[tab1])

# Hiding sliders initially (refer to callback.js to see visibility conditions)
pulse_inj_sl.visible = False
rho_s_sl.visible = False
Kd_sl.visible = False

# Work with template in order to modify html code
script, (div1, div2, div3, div4) = components((COLp,layout1,BTCp,layout2))

# Add hmtl lines
f = open("./themodel.js", "w")
script = "\n".join(script.split("\n")[2:-1])
f.write(script)
f.close()

# Read in the template file
with open('template', 'r') as file :
  filedata = file.read()

# Replace the target strings (object in html is "placeholder")
filedata = filedata.replace('+placeholder1+', div1)
filedata = filedata.replace('+placeholder2+', div2)
filedata = filedata.replace('+placeholder3+', div3)
filedata = filedata.replace('+placeholder4+', div4)

# Write to html file
with open('index.html', 'w') as file:
  file.write(filedata)
