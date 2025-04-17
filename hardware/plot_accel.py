import matplotlib.pyplot as plt
import csv

log_path = "/home/camcs/rewrite_these_twinks/hardware/accel_data/accel_data_log.csv"

timestamps = []
y_vals = []
z_vals = []
emay_v = []
emaz_v = []
y_tol_l = []
y_tol_u = []
z_tol_l = []
z_tol_u = []

with open(log_path, 'r') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) == 3:
            #t, y, z = map(float, row)
            timestamps.append(float(row[0]))
            y_vals.append(float(row[1]))
            z_vals.append(float(row[2]))
            ema = False
        if len(row) > 3:
            timestamps.append(float(row[0]))
            y_vals.append(float(row[1]))
            z_vals.append(float(row[2]))
            emay_v.append(float(row[3]))
            emaz_v.append(float(row[4]))
            y_tol_u.append(float(row[5]))
            y_tol_l.append(float(row[6]))
            z_tol_u.append(float(row[7]))
            z_tol_l.append(float(row[8]))
            ema = True


#self.y_tol_u, self.y_tol_l, self.z_tol_u, self.z_tol_l])
#plt.figure(figsize=(10, 6))
plt.plot(timestamps, y_vals, label='Y-axis')
plt.plot(timestamps, z_vals, label='Z-axis')
plt.plot(timestamps, emay_v, label='Filtered-Y')
plt.plot(timestamps, emaz_v, label='Filtered-Z')
plt.plot(timestamps, y_tol_u, label='Y Bound Upper')
plt.plot(timestamps, y_tol_l, label='Y Bound Lower')
plt.plot(timestamps, z_tol_u, label='Z Bound Upper')
plt.plot(timestamps, z_tol_l, label='Z Bound Lower')
plt.xlabel("Time (s)")
plt.ylabel("Acceleration (g)")
plt.title("Accelerometer Data Over Time")
plt.legend()
plt.savefig("accel_plot.png")