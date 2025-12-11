# import pandas as pd
# from sklearn.linear_model import LinearRegression
# from weekly.models import WeeklyRecord
# import numpy as np

# def predict_inventory(product, weeks=4):
#     records = WeeklyRecord.objects.filter(product=product).order_by('year','week_no')
#     if records.count()<2:
#         return []
#     data = pd.DataFrame([{'week':r.year*100+r.week_no,'inventory':r.inventory} for r in records])
#     X = np.array(range(len(data))).reshape(-1,1)
#     y = data['inventory'].values
#     model = LinearRegression().fit(X,y)
#     predictions = [round(model.predict([[i]])[0],2) for i in range(len(data), len(data)+weeks)]
#     return predictions
