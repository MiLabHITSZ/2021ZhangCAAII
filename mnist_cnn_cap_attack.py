import tensorflow as tf
from tensorflow import keras
from test_process import *
from attack import *
import math


def preprocess_mnist_cnn(x_in, y_in):
    x_in = tf.cast(x_in, dtype=tf.float32) / 255
    y_in = tf.cast(y_in, dtype=tf.int32)
    y_in = tf.one_hot(y_in, depth=10)
    return x_in, y_in


def mal_mnist_cnn_enhance_synthesis(input_shape, num_target, class_num):
    num_target = int(num_target / 2)  # 算出可以窃取的像素数

    mal_x_out = []
    mal_y_out = []
    for j in range(num_target, num_target + class_num):
        for k in range(20):
            # initialize a empty image
            x = np.zeros(input_shape[1:]).flatten()
            # simple & naive deterministic value for two pixel
            x[k] = (j + 1) * 255
            if k < int(32 * 32) - 1:
                x[k + 1] = (j + 1) * 255
            else:
                x[0] = (j + 1) * 255
            mal_x_out.append(x)
            mal_y_out.append(k % 10)

    mal_x_out = np.asarray(mal_x_out, dtype=np.float32)
    mal_y_out = np.asarray(mal_y_out, dtype=np.int32)

    shape = [-1] + list(input_shape[1:])
    mal_x_out = mal_x_out.reshape(shape)
    # mal_y_out_copy = np.random.randint(0, 10, size=(200,))
    # print(mal_y_out_copy)
    return mal_x_out, mal_y_out


def mnist_cnn_cap_train(model, optimizer):
    number = 2
    (x_train, y_train), (x_test, y_test) = datasets.mnist.load_data()

    # 合成恶意数据进行CAP攻击
    x_mal1, y_mal1 = mal_mnist_fnn_synthesis(x_train, number, 4)
    x_mal1 = x_mal1.reshape(-1, 28, 28)
    x_mal2, y_mal2 = mal_mnist_cnn_enhance_synthesis(x_train.shape, number, 10)
    x_mal2 = x_mal2.reshape(-1, 28, 28)

    # 展示原始结果
    recover_label_data(y_mal1, 'mnist')

    # 对合成的恶意数据进行拼接
    x_train = np.vstack((x_train, x_mal1, x_mal2))
    y_train = np.append(y_train, y_mal1)
    y_train = np.append(y_train, y_mal2)
    print(x_train.shape)
    print(y_train.shape)

    # 对训练集、测试集、恶意扩充数据集1、2进行预处理
    train_db = tf.data.Dataset.from_tensor_slices((x_train, y_train))
    train_db = train_db.shuffle(10000).map(preprocess_mnist_cnn).batch(128)

    test_db = tf.data.Dataset.from_tensor_slices((x_test, y_test))
    test_db = test_db.map(preprocess_mnist_cnn).batch(128)

    mal_db1 = tf.data.Dataset.from_tensor_slices((x_mal1, y_mal1))
    mal_db1 = mal_db1.shuffle(10000).map(preprocess_mnist_cnn).batch(128)

    mal_db2 = tf.data.Dataset.from_tensor_slices((x_mal2, y_mal2))
    mal_db2 = mal_db2.shuffle(10000).map(preprocess_mnist_cnn).batch(128)

    # 对生成的恶意扩充数据集进行预处理
    x_mal1, y_mal1 = preprocess_mnist_cnn(x_mal1, y_mal1)
    x_mal2, y_mal2 = preprocess_mnist_cnn(x_mal2, y_mal2)

    # 定义一系列的列表存储结果
    acc_list = []
    mal1_acc_list = []
    mal2_acc_list = []
    MAPE_list = []
    cross_entropy_list = []

    # 训练过程
    for epoch in range(300):
        for step, (x_batch, y_batch) in enumerate(train_db):
            with tf.GradientTape() as tape:
                out = model(x_batch, training=True)
                # out = tf.squeeze(out, axis=[1, 2])
                loss = tf.reduce_mean(keras.losses.categorical_crossentropy(y_batch, out, from_logits=True))
                # print(float(loss))
            # 对所有参数求梯度
            grads = tape.gradient(loss, model.trainable_variables)
            # 自动更新
            optimizer.apply_gradients(zip(grads, model.trainable_variables))
        loss_print = float(loss)
        # 获取测试集准确率
        acc = mnist_cnn_test(model, test_db)
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
            result[int(i / 20)][out_numpy[i]] += 1
        result = result / 20
        cross_entropy = 0
        for i in range(10):
            for j in range(10):
                if result[i][j] != 0:
                    cross_entropy += -result[i][j] * math.log(result[i][j])
        cross_entropy_list.append(cross_entropy)

        print('epoch:', epoch, 'loss:', loss_print, 'Evaluate Test Acc:', float(acc), 'Evaluate mal1 Acc:',
              float(mal1_acc), 'Evaluate mal2 Acc:', float(mal2_acc), 'MAPE:', float(MAPE), 'Mean_cross_entropy',
              float(cross_entropy))

    # 展示扩充数据集1的窃取效果
    mal_y_pred = model(x_mal1)
    pred = tf.argmax(mal_y_pred, axis=1)
    recover_label_data(pred.numpy(), 'mnist')

    # 展示恶意扩充数据集2的窃取结果
    mal2_pred = model(x_mal2, training=True)
    out = tf.argmax(mal2_pred, axis=1)
    out_numpy = out.numpy()
    result = np.zeros((10, 10))
    for i in range(200):
        result[i % 10][out_numpy[i]] += 1
    np.save('result', result)
    print(result)
    # mal_y_pred = model(mal_x)
    # pred = tf.argmax(mal_y_pred, axis=1)
    # recover_label_data(pred.numpy(), 'mnist')