"""Validated data merges without interpolation, aggregation or source modification."""
from pathlib import Path
import numpy as np
import pandas as pd


def merge_tables(inputs,mode=0):
    if len(inputs)<2: raise ValueError('Select at least two datasets')
    if mode==0:
        columns=list(inputs[0][1].df.columns)
        if any(set(t.df.columns)!=set(columns) for _,t in inputs):
            raise ValueError('Append requires matching column names. Map or rename columns first.')
        frames=[]
        source='Source file'
        while source in columns: source='_'+source
        for path,table in inputs:
            frame=table.df[columns].copy(); frame[source]=Path(path).name; frames.append(frame)
        return pd.concat(frames,ignore_index=True)
    result=None; used=set()
    for index,(path,table) in enumerate(inputs):
        if table.x is None or not table.ys: raise ValueError('Each file needs a mapped X column and Y values')
        x=table.arr(table.x)
        if not np.isfinite(x).all() or len(np.unique(x))!=len(x):
            raise ValueError(f'{Path(path).name}: X values must be finite and unique for a column join')
        if result is not None and (len(x)!=len(result) or not np.array_equal(x,result.iloc[:,0].to_numpy())):
            raise ValueError('Column joins require identical X values in identical order. Align the data first; no interpolation is applied automatically.')
        frame=pd.DataFrame({inputs[0][1].x:x})
        for col in table.ys:
            name=f'{Path(path).stem}: {col}'; original=name; n=2
            while name in used: name=f'{original} ({n})'; n+=1
            used.add(name); frame[name]=table.arr(col)
        result=frame if result is None else pd.concat([result,frame.iloc[:,1:]],axis=1)
    return result
