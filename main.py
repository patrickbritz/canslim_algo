from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Indicators")


from System import *
from QuantConnect import *
from QuantConnect.Indicators import *
from QuantConnect.Data import *
from QuantConnect.Data.Market import *
from QuantConnect.Data.Custom import *
from QuantConnect.Algorithm import *
from QuantConnect.Python import *
from collections import deque
import numpy as np
import math

# generic helpers

def GetMinIdx(lst):
    return min(range(len(lst)), key=lst.__getitem__)

def GetMaxIdx(lst):
    return max(range(len(lst)), key=lst.__getitem__)

def AggExtremaIdx(input_lst, start_at, min_len, max_len, op='min'):
    outer_lst = list(input_lst)
    sub_range_endpoint = min(start_at + max_len, len(outer_lst))
    sub_range_start_point = min(start_at + min_len, sub_range_endpoint)
    inner_lst = outer_lst[sub_range_start_point:sub_range_endpoint]
    if len(inner_lst) > 0:
        if op == 'min':
            idx_rel_extrema = GetMinIdx(inner_lst)
        else:
            idx_rel_extrema = GetMaxIdx(inner_lst)
        idx_abs_extrema = start_at + min_len + idx_rel_extrema
        return idx_abs_extrema
    else:
        return None
    



# https://www.haikulabs.com/CwH_SearchAlg.htm
class CupAndHandle():
    def __init__(self, name, period):
        self.Name = name
        self.Value = 0
        
        self.IsReady = False
        
        # pattern base definition
        self.MinLen = 27
        self.MaxLen = 252
        self.SetupFrameMinLen = 2
        self.SetupFrameMaxLen = 50
        self.LeftCupFrameMinLen = 20
        self.LeftCupFrameMaxLen = 147
        self.RightCupFrameMinLen = 3
        self.RightCupFrameMaxLen = 25
        self.HandleFrameMinLen = 2
        self.HandleFrameMaxLen = 30
        
        # hard coded period for now
        period = self.MaxLen
        
        self.prices = deque(maxlen=period)
        self.volumes = deque(maxlen=period)
        self.rpv = deque(maxlen=period-1)
        self.rpvk = deque(maxlen=period-1)
        self.CurrentLength = len(self.prices)
        
        
        
    # Update method is mandatory
    def Update(self, input):
        #add value to rolling window
        if len(self.prices) > 0:
            self.IsReady = True
            self.previous_price = self.prices[0]
            current_rpv = (input.Price-self.previous_price)/self.previous_price
            current_rpvk = current_rpv*input.Volume
            self.rpv.appendleft(current_rpv)
            self.rpvk.appendleft(current_rpvk)
            
        self.prices.appendleft(input.Price)
        self.volumes.appendleft(input.Volume)

        
        test_passed = self.EvaluateForCupHandle()
        if test_passed:
            self.Value = 1
        else:
            self.Value = 0
        
    def EvaluateForCupHandle(self):
        pattern_pass = False
        if len(self.prices) >= self.MinLen:
            dict_price_points = self.CandidatePointIndexExtraction(self.prices)
            dict_vol_points = self.CandidatePointIndexExtraction(self.volumes)
            print("price points:")
            print(dict_price_points)
            print("vol points:")
            print(dict_vol_points)
            if dict_price_points is not None and dict_vol_points is not None:
                price_pass, type_cup = self.PriceRequirements(dict_price_points)
                if price_pass:
                    pattern_pass = True
                    r1, r2, r3 = self.VolumeCharacteristics(dict_vol_points)
                    if np.all([r1 > 0, r2 > 0, r3 > 0]):
                        rank = r1 + r2 + r3
                        if rank > 6:
                            pattern_pass = True
        return pattern_pass
                        
            
            
     
     
    def VolumeCharacteristics(self, dict_points):
        values = list(self.volumes)
        k_idx = dict_points['k']
        a_idx = dict_points['a']
        b_idx = dict_points['b']
        c_idx = dict_points['c']
        d_idx = dict_points['d']
        
        k = values[k_idx]
        a = values[a_idx]
        b = values[b_idx]
        c = values[c_idx]
        d = values[d_idx]        
        
        # arpv can't be 0
        urpv3, drpv3, arpv3 = self.FrameRPV(b_idx, c_idx)
        urpv4, drpv4, _ = self.FrameRPV(c_idx, d_idx)
        _, _, arpv = self.FrameRPV(0, len(self.rpvk))
        
        r1 = math.log(urpv3/drpv3)
        r2 = math.log(urpv3/drpv4)
        r3 = math.log(urpv3/arpv)
        return r1, r2, r3
   
            
    
    
    def FrameRPV(self, start_idx, end_idx):    
        frame_rpv = list(self.rpvk)[start_idx:end_idx] #inclusive of c, but adjusted for rpvk index being -1
        frame_rpv_pos = [frame_rpv[i] for i in range(len(frame_rpv)) if frame_rpv[i] > 0]
        frame_rpv_neg = [frame_rpv[i] for i in range(len(frame_rpv)) if frame_rpv[i] < 0]
        if len(frame_rpv_pos) > 0: 
            urpv = sum(frame_rpv_pos)/len(frame_rpv_pos)
        else :
            urpv = 0 # should this be null or returned as none?
        if len(frame_rpv_neg) > 0:
            drpv = abs(sum(frame_rpv_pos))/len(frame_rpv_neg)      
        else:
            drpv = 0 #samesies
        if len(frame_rpv) > 0:
            arpv = sum(frame_rpv)/len(frame_rpv)
        else:
            arpv = 0
        return urpv, drpv, arpv
        
        
            
    def PriceRequirements(self, dict_points):
        values = list(self.prices)
        k_idx = dict_points['k']
        a_idx = dict_points['a']
        b_idx = dict_points['b']
        c_idx = dict_points['c']
        d_idx = dict_points['d']
        
        k = values[k_idx]
        a = values[a_idx]
        b = values[b_idx]
        c = values[c_idx]
        d = values[d_idx]
        
        pivot_rat = c/a
        d_c_rat = d/c
        
        type_cup = ""

        pattern_pass = False
        if k < a and b < c and b < a and d <= c:
            if 0.78 < pivot_rat and 1.1 >= pivot_rat:
                type_cup = "high"
            if 0.25 < pivot_rat and 78 >= pivot_rat:
                type_cup = "low"
            if type_cup in ("high", "low"):
                a_c = values[a_idx : c_idx+1]
                all_j_pass = np.all(map(lambda j_idx: values[j_idx] < ((j_idx-a_idx)/(c_idx-a_idx))*(c-a), a_c))
                if all_j_pass and d > 0.5*(c-b):
                    pattern_pass = True
        return pattern_pass, type_cup 
            
            
    def CandidatePointIndexExtraction(self, input):
        a = AggExtremaIdx(input, 0, self.SetupFrameMinLen, self.SetupFrameMaxLen, op='max')
        
        # check to make sure we have enough points to continue
        points_remaining = len(input) - a + 1
        min_points_needed = self.LeftCupFrameMinLen + self.RightCupFrameMinLen + self.HandleFrameMinLen
        if points_remaining < min_points_needed:
            print("not enough points, section 1")
            return None
       
        k = AggExtremaIdx(input, 0, 0, a - 1, op='min')
        if k is None:
            return None

        min_start_point_c = a + self.LeftCupFrameMinLen + 1
        c = AggExtremaIdx(input, min_start_point_c, self.RightCupFrameMinLen, self.RightCupFrameMaxLen, op='max')

        # time to test again to ensure we have enough points left!
        if c is None:
            return None
            
        # ensure we have enough points after c
        points_remaining_after_c = len(input) - c + 1
        min_points_needed_after_c = self.HandleFrameMinLen
        if points_remaining_after_c < min_points_needed_after_c:
            print("not enough points section 2")
            return None
            
        # ensure we have enough poitns before c
        if (c-a) <= self.LeftCupFrameMinLen:
            return None
 
        # find point B, which is the low point of the right cup and the end of the left cup

        c_frames = min(c - self.RightCupFrameMinLen - min_start_point_c, self.LeftCupFrameMaxLen - self.LeftCupFrameMinLen)
        b = AggExtremaIdx(input, min_start_point_c, 0, c_frames, op='min')

        if b is None:
            return None

        points_between_cups = b - a + 1
        min_points_needed_between_cups = self.LeftCupFrameMinLen
        if points_between_cups < min_points_needed_between_cups:
            print("not enough points section 3")
            return None
        
        # finally point D is the min point in the potential handle 
        d = AggExtremaIdx(input, c+1, self.HandleFrameMinLen, self.HandleFrameMaxLen, op='min')

        if d is None:
            return None
        
        dict_points = {}
        if k is None or a is None or b is None or c is None or d is None:
            dict_points = None
        else:
            dict_points['k'] = k
            dict_points['a'] = a
            dict_points['b'] = b
            dict_points['c'] = c
            dict_points['d'] = d

        return dict_points
        
        


class CanSlimAlgo(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020, 1, 14)  # Set Start Date
        self.SetEndDate(2021, 1, 18)
        self.SetCash(100000)  # Set Strategy Cash
        self.AddEquity("IDEX", Resolution.Daily)

        
        self.chWindow = RollingWindow[float](252)
        

        stockPlot = Chart('IDEX Cup and Handle Test')
        # On the Trade Plotter Chart we want 3 series: trades and price:
        stockPlot.AddSeries(Series('Buy', SeriesType.Scatter, 0))
        stockPlot.AddSeries(Series('Sell', SeriesType.Scatter, 0))
        stockPlot.AddSeries(Series('Price', SeriesType.Line, 0))

        self.AddChart(stockPlot)        
        volumePlot = Chart('IDEXCup and Handle Volume')
        volumePlot.AddSeries(Series('IDEX Vol', SeriesType.Bar,0))
        
        

        self.cuphandle = CupAndHandle('IDEX', 60)

        # The python custom class must inherit from PythonIndicator to enable Updated event handler
        #self.custom.Updated += self.CustomUpdated

        #self.customWindow = RollingWindow[IndicatorDataPoint](5)
        
        self.RegisterIndicator("IDEX", self.cuphandle, Resolution.Daily)
        self.PlotIndicator('ch', self.cuphandle)        

        
        

    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.
            Arguments:
                data: Slice object keyed by symbol containing the stock data
        '''
        
        if data.ContainsKey("IDEX"):
            self.Plot('IDEX Cup and Handle Test', 'Price', data['IDEX'].Close)
            #self.Plot('IDEX Cup and Handle Test', 'Max Val', self.maxv.Current.Value)
            #self.Plot('IDEX Cup and Handle Test', 'Min Val', self.minv.Current.Value)
            #self.Plot('IDEX Cup and Handle Volume', 'Vol', data['IDEX'].Volume)
            
            self.chWindow.Add(data["IDEX"].Close)
            
            #wmax = max(self.chWindow)
            
            #self.Plot('Max Rolling Window', "Max", wmax)