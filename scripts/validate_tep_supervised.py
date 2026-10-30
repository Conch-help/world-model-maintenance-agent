"""Supervised TEP fault detection and type classification with held-out batches."""
from __future__ import annotations
import json, re, os
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report


def read_features(path: Path, step: int = 20, window: int = 10):
    df = pd.read_excel(path)
    arr = df.drop(columns=[df.columns[0]]).iloc[::step].to_numpy(dtype=float)
    feats=[]
    for i in range(len(arr)):
        start=max(0,i-window+1)
        chunk=arr[start:i+1]
        feats.append(np.concatenate([chunk.mean(axis=0), chunk.std(axis=0), arr[i]]))
    return np.asarray(feats,dtype=np.float32)


def main():
    root=Path(os.environ.get('TEP_DATA_ROOT', Path('..') / 'work' / 'public_data')) / 'tennessee-eastman-dataset' / 'simulations' / 'mode_1'
    normal=read_features(root/'mode1_normal_500.xlsx')
    n_half=len(normal)//2
    x_train_n, x_test_n=normal[:n_half], normal[n_half:]
    fault_paths={}
    for p in sorted((root/'faults').glob('mode1_*.xlsx')):
        m=re.match(r'mode1_(\d+)_(\d+)\.xlsx$',p.name)
        if m: fault_paths.setdefault(int(m.group(1)),[]).append(p)
    x_train_f=[]; y_train_f=[]; x_test_f=[]; y_test_f=[]; x_test_n_sup=[]
    for fault,paths in sorted(fault_paths.items()):
        for i,p in enumerate(paths):
            f=read_features(p)
            if i<5:
                x_train_f.append(f); y_train_f.extend([fault]*len(f))
            else:
                x_test_f.append(f); y_test_f.extend([fault]*len(f))
    x_train_f=np.vstack(x_train_f); y_train_f=np.asarray(y_train_f)
    x_test_f=np.vstack(x_test_f); y_test_f=np.asarray(y_test_f)
    # Binary normal-vs-fault detector.
    xb=np.vstack([x_train_n,x_train_f])
    yb=np.concatenate([np.zeros(len(x_train_n),dtype=int),np.ones(len(x_train_f),dtype=int)])
    det=HistGradientBoostingClassifier(max_iter=100,learning_rate=0.08,random_state=20261008)
    det.fit(xb,yb)
    pred_n=det.predict(x_test_n); pred_f=det.predict(x_test_f)
    false_positive=float(np.mean(pred_n==1)); detection_rate=float(np.mean(pred_f==1))
    # 21-class fault type classifier.
    typ=HistGradientBoostingClassifier(max_iter=100,learning_rate=0.08,random_state=20261008)
    typ.fit(x_train_f,y_train_f)
    pred_type=typ.predict(x_test_f)
    report={
        'dataset':'Tennessee Eastman Process Mode 1',
        'source':'Blound04/tennessee-eastman-dataset (MIT)',
        'split':'first 5 batches per fault for training; remaining batches held out',
        'binary_detector':{
            'normal_false_positive_rate':false_positive,
            'fault_detection_rate':detection_rate,
        },
        'fault_type_classifier':{
            'accuracy':float(accuracy_score(y_test_f,pred_type)),
            'macro_f1':float(f1_score(y_test_f,pred_type,average='macro')),
            'weighted_f1':float(f1_score(y_test_f,pred_type,average='weighted')),
            'n_test':int(len(y_test_f)),
            'classification_report':classification_report(y_test_f,pred_type,output_dict=True,zero_division=0),
        },
        'boundary':'TEP is a public process simulation benchmark, not a real production DCS dataset.',
    }
    out=Path('artifacts/tep_supervised_validation.json'); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['binary_detector','fault_type_classifier']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
