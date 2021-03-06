from tensorflow import keras
from test_process import *
from attack import *
from tensorflow.keras import datasets
from load_data import *
from encoding import *
from decoding import *
from draw_picture import *
import math
import csv
import codecs

def data_write_csv(file_name, datas):  # file_name为写入CSV文件的路径，datas为要写入数据列表
    file_csv = codecs.open(file_name, 'w+', 'utf-8')  # 追加
    writer = csv.writer(file_csv, delimiter=' ', quotechar=' ', quoting=csv.QUOTE_MINIMAL)
    for data in datas:
        writer.writerow(data)
    print("保存文件成功，处理结束")

# 执行自定义训练过程
def fashion_mnist_fnn_cap_attack_train(model, optimizer):
    # 初始化模型
    model.build(input_shape=[128, 784])
    number = 20
    total_epoch = 0
    (x_train, y_train), (x_test, y_test) = datasets.fashion_mnist.load_data()
    # 合成恶意数据进行CAP攻击
    x_mal1, y_mal1 = mal_mnist_fnn_synthesis(x_train, number, 4)
    x_mal2, y_mal2 = mal_mnist_enhance_synthesis(x_train.shape, number, 10)

    # 展示原始结果
    recover_label_data(y_mal1, 'mnist')

    print(x_mal1.shape)
    # 对合成的恶意数据进行拼接
    x_train = np.vstack((x_train, x_mal1, x_mal2))
    y_train = np.append(y_train, y_mal1)
    y_train = np.append(y_train, y_mal2)
    print(x_train.shape)
    print(y_train.shape)

    # 对训练集、测试集、恶意扩充数据集1、2进行预处理，获取其准确率
    train_db = tf.data.Dataset.from_tensor_slices((x_train, y_train))
    train_db = train_db.shuffle(10000).map(preprocess_mnist).batch(128)

    test_db = tf.data.Dataset.from_tensor_slices((x_test, y_test))
    test_db = test_db.map(preprocess_mnist).batch(128)

    mal_db1 = tf.data.Dataset.from_tensor_slices((x_mal1, y_mal1))
    mal_db1 = mal_db1.shuffle(10000).map(preprocess_mnist).batch(128)

    mal_db2 = tf.data.Dataset.from_tensor_slices((x_mal2, y_mal2))
    mal_db2 = mal_db2.shuffle(10000).map(preprocess_mnist).batch(128)

    # 对生成的恶意扩充数据集进行预处理
    x_mal1, y_mal1 = preprocess_mnist(x_mal1, y_mal1)
    x_mal2, y_mal2 = preprocess_mnist(x_mal2, y_mal2)

    # 定义一系列的列表存储结果
    loss_list = []
    acc_list = []
    mal1_acc_list = []
    mal2_acc_list = []
    MAPE_list = []
    cross_entropy_list = []
    # 执行训练过程
    for epoch in range(1000):
        total_epoch += 1
        for step, (x_batch, y_batch) in enumerate(train_db):
            with tf.GradientTape() as tape:
                out = model(x_batch, training=True)
                out = tf.squeeze(out)

                # 计算损失函数
                loss = tf.reduce_mean(keras.losses.categorical_crossentropy(y_batch, out, from_logits=False))
                loss_print = float(loss)

            # 执行梯度下降
            grads = tape.gradient(loss, model.trainable_variables)
            optimizer.apply_gradients(zip(grads, model.trainable_variables))

        # 获得对测试集的准确率
        acc = test(model, test_db)
        acc_list.append(float(acc))

        # 获得恶意扩充数据集1、2的准确率
        mal1_acc = test_mal(model, mal_db1, number, 'mal1')
        mal2_acc = test_mal(model, mal_db2, number, 'mal2')
        mal1_acc_list.append(float(mal1_acc))
        mal2_acc_list.append(float(mal2_acc))

        # 计算MAPE
        mal_y_pred = model(x_mal1)
        pred = tf.argmax(mal_y_pred, axis=1)
        data = np.zeros(int(pred.shape[0] / 2))
        for i in range(len(data)):
            data[i] = pred[2 * i] + pred[2 * i + 1]
            data[i] = data[i] * (2 ** 4)
            if data[i] > 255:
                data[i] = 255
        x_train = x_train.flatten()
        x_train = x_train[0:data.shape[0]]
        assert x_train.shape == data.shape
        MAPE = np.mean(np.abs(x_train - data))
        MAPE_list.append(MAPE)

        # 计算平均交叉熵
        mal2_pred = model(x_mal2, training=True)
        out = tf.argmax(mal2_pred, axis=1)
        out_numpy = out.numpy()
        result = np.zeros((10, 10))
        for i in range(200):
            result[i % 10][out_numpy[i]] += 1
        result = result/20
        cross_entropy = 0
        for i in range(10):
            for j in range(10):
                if result[i][j] != 0:
                    cross_entropy += -result[i][j]*math.log(result[i][j])
        cross_entropy_list.append(cross_entropy)
        print('epoch:', epoch, 'loss:', loss_print, 'Evaluate Test Acc:', float(acc), 'Evaluate mal1 Acc:',
              float(mal1_acc), 'Evaluate mal2 Acc:', float(mal2_acc), 'MAPE:', float(MAPE), 'Mean_cross_entropy', float(cross_entropy))
        # 训练停止条件
        if float(mal1_acc) > 0.995:
            break

    # 保存结果
    np.save('fashion_mnist_acc', np.array(acc_list))
    np.save('fashion_mnist_mal1_acc', np.array(mal1_acc_list))
    np.save('fashion_mnist_mal2_acc', np.array(mal2_acc_list))
    np.save('fashion_mnist_mape', np.array(MAPE_list))
    np.save('fashion_mnist_cross_entropy', np.array(cross_entropy_list))

    # 输入恶意扩充集2并得到预测标签编码
    mal2_pred = model(x_mal2, training=True)
    out = tf.argmax(mal2_pred, axis=1)
    out_numpy = out.numpy()

    # 将恶意数据集2的标签编码改为用户制定的编码
    mal2_encode = encoding_mapping(out_numpy)
    print(mal2_encode)

    # 攻击者获取数据持有者指定的编码与标签编码的对应关系
    relation = recover(mal2_encode)

    # 攻击者输入扩充数据集1并得到预测标签编码
    mal_y_pred = model(x_mal1)
    pred = tf.argmax(mal_y_pred, axis=1)

    # 数据拥有者将恶意扩充集1的预测标签编码根据对应关系转成数据拥有者指定的编码
    mal1_encode = encoding_mapping(pred.numpy())

    # 攻击者利用对应关系将恶意扩充集1的指定编码转成预测标签编码
    mal1_decode = []
    for i in mal1_encode:
        mal1_decode.append(relation[i])
    mal1_decode = np.array(mal1_decode)
    np.save('fashion_mnist_stolen_data', mal1_decode)

    # 将预测标签编码恢复成图片
    recover_label_data(mal1_decode, 'mnist')

    # 画图
    draw(total_epoch, acc_list, mal1_acc_list, mal2_acc_list, MAPE_list, cross_entropy_list, 'Fashion-MNIST')
    # 展示测试集、扩充数据集1、扩充数据集2的准确率
    # plt.figure()
    # X = np.arange(0, total_epoch)
    # plt.plot(X, acc_list, label="test accuracy", linestyle=":")
    # plt.plot(X, mal1_acc_list, label="mal1 accuracy", linestyle="--")
    # plt.plot(X, mal2_acc_list, label="mal2 accuracy", linestyle="-.")
    # plt.legend()
    # plt.title("Accuracy distribution")
    # plt.xlabel("epoch")
    # plt.ylabel("accuracy")
    # plt.show()
    # plt.close()

    # 展示MAPE 平均交叉熵变化
    # plt.figure()
    # X = np.arange(0, total_epoch)
    # plt.plot(X, MAPE_list, label="MAPE", linestyle=":")
    # plt.plot(X, cross_entropy_list, label="cross entropy", linestyle="--")
    # plt.legend()
    # plt.title("MAPE and Cross entropy distribution")
    # plt.xlabel("epoch")
    # plt.ylabel("VALUE")
    # plt.show()
